from __future__ import annotations

import hashlib
import html
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.sse_parser import iter_sse_events


@dataclass(frozen=True)
class BridgeToolInvocation:
    req_id: str
    agent_id: str
    tool_name: str
    tool_call_id: str | None = None


@dataclass(frozen=True)
class BridgeToolResult:
    ok: bool
    exit_code: int
    canceled: bool
    result_json: Any | None
    error: dict[str, Any] | None


def bridge_tools_to_openai_tools(bridge_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Backward-compatible helper for single-agent mode.
    """
    openai_tools, _ = bridge_tools_by_agent_to_openai_tools(
        bridge_tools_by_agent={"__single__": bridge_tools or []},
        force_plain_tool_names=True,
    )
    return openai_tools


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_\\-]+")


def _sanitize_name(value: str) -> str:
    s = (value or "").strip()
    s = s.replace(".", "_").replace(":", "_").replace("/", "_").replace("\\", "_")
    s = s.replace("-", "_")
    s = _SAFE_NAME_RE.sub("_", s)
    s = s.strip("_")
    return s or "tool"


def _make_tool_alias(*, agent_id: str, tool_name: str, max_len: int = 64) -> str:
    agent_part = _sanitize_name(agent_id)[:16]
    tool_part = _sanitize_name(tool_name)[:32]
    h = hashlib.sha1(f"{agent_id}:{tool_name}".encode()).hexdigest()[:10]

    base = f"bridge__{agent_part}__{tool_part}__{h}"
    if len(base) <= max_len:
        return base
    # Extremely conservative fallback.
    return f"bridge__{h}"


def bridge_tools_by_agent_to_openai_tools(
    *,
    bridge_tools_by_agent: dict[str, list[dict[str, Any]]],
    force_plain_tool_names: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    """
    Convert Bridge tools to OpenAI function tools.

    Returns:
      (openai_tools, tool_name_map)
        - openai_tools: list of {"type":"function", ...}
        - tool_name_map: openai_tool_name -> (agent_id, bridge_tool_name)
    """
    tools: list[dict[str, Any]] = []
    tool_name_map: dict[str, tuple[str, str]] = {}

    # If only one agent is present, keep the original tool names for stability.
    agent_ids = [k for k in (bridge_tools_by_agent or {}).keys() if k != "__single__"]
    single_agent = len(agent_ids) == 1

    for agent_id, bridge_tools in (bridge_tools_by_agent or {}).items():
        if not isinstance(bridge_tools, list):
            continue
        for t in bridge_tools or []:
            if not isinstance(t, dict):
                continue
            raw_name = str(t.get("name") or "").strip()
            if not raw_name:
                continue
            input_schema = t.get("input_schema")
            if not isinstance(input_schema, dict):
                input_schema = {"type": "object", "properties": {}}

            if force_plain_tool_names or single_agent:
                openai_name = raw_name
            else:
                openai_name = _make_tool_alias(agent_id=agent_id, tool_name=raw_name)
                tool_name_map[openai_name] = (agent_id, raw_name)

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": openai_name,
                        "description": str(t.get("description") or ""),
                        "parameters": input_schema,
                    },
                }
            )

    return tools, tool_name_map


def _safe_json_loads(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return None


_FUNC_TRIGGER_RE = re.compile(r"FUNC_TRIGGER_[^\s]*?_END", re.IGNORECASE)
_FUNCTION_CALLS_BLOCK_RE = re.compile(
    r"<function_calls>(?P<body>[\s\S]*?)(?:</function_calls>|\Z)",
    re.IGNORECASE,
)
_FUNCTION_CALL_BLOCK_RE = re.compile(
    r"<function_call>(?P<body>[\s\S]*?)(?:</function_call>|\Z)",
    re.IGNORECASE,
)
_SIMPLE_TAG_RE = re.compile(
    r"<(?P<tag>[a-zA-Z0-9_\-]+)>(?P<value>[\s\S]*?)</(?P=tag)>",
    re.IGNORECASE,
)


def _extract_text_from_content_field(content: Any) -> str | None:
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str) and part:
                parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            if isinstance(part.get("text"), str) and part["text"]:
                parts.append(part["text"])
                continue
            if isinstance(part.get("text"), dict):
                value = part["text"].get("value")
                if isinstance(value, str) and value:
                    parts.append(value)
        joined = "".join(parts).strip()
        if joined:
            return joined
    return None


def _coerce_scalar(value: str) -> Any:
    raw = html.unescape((value or "").strip())
    if raw == "":
        return ""
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if re.fullmatch(r"-?\d+", raw):
        try:
            return int(raw)
        except Exception:
            return raw
    if re.fullmatch(r"-?\d+\.\d+", raw):
        try:
            return float(raw)
        except Exception:
            return raw
    return raw


def _merge_arg_value(target: dict[str, Any], key: str, value: Any) -> None:
    if key in target:
        current = target[key]
        if isinstance(current, list):
            current.append(value)
        else:
            target[key] = [current, value]
        return
    target[key] = value


def _parse_args_xmlish(value: str) -> dict[str, Any]:
    """
    Parse a best-effort "XML-ish" args payload:
      <query>foo</query><max_results>10</max_results>
    Supports nested tags via recursion. Falls back gracefully.
    """
    text = (value or "").strip()
    if not text:
        return {}

    # JSON wins if the model provided it.
    if text.startswith("{") or text.startswith("["):
        parsed = _safe_json_loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {}

    args: dict[str, Any] = {}
    for m in _SIMPLE_TAG_RE.finditer(text):
        key = str(m.group("tag") or "").strip()
        if not key:
            continue
        inner = str(m.group("value") or "")
        inner_stripped = inner.strip()
        # If nested tags exist, attempt recursion; otherwise coerce scalar.
        if "<" in inner_stripped and _SIMPLE_TAG_RE.search(inner_stripped):
            _merge_arg_value(args, key, _parse_args_xmlish(inner_stripped))
        else:
            _merge_arg_value(args, key, _coerce_scalar(inner_stripped))
    return args


def _extract_tool_calls_from_tagged_text(text: str) -> list[dict[str, Any]]:
    """
    Fallback extractor for models that emit tool calls as plain text tags, e.g.
      FUNC_TRIGGER_xxx_END <function_calls> ... </function_calls>
    """
    if not isinstance(text, str) or not text.strip():
        return []

    # Heuristic gate: avoid scanning every response.
    if "<function_call" not in text.lower() and "func_trigger_" not in text.lower():
        return []

    # Prefer the explicit <function_calls> wrapper; otherwise scan the whole tail.
    scan = text
    block = _FUNCTION_CALLS_BLOCK_RE.search(text)
    if block:
        scan = block.group("body") or ""
    else:
        idx = text.lower().find("<function_call")
        if idx >= 0:
            scan = text[idx:]

    tool_calls: list[dict[str, Any]] = []
    for m in _FUNCTION_CALL_BLOCK_RE.finditer(scan):
        body = str(m.group("body") or "")
        tool_m = re.search(r"<tool>(?P<name>[\s\S]*?)</tool>", body, re.IGNORECASE)
        tool_name = str(tool_m.group("name") if tool_m else "").strip()
        if not tool_name:
            continue

        args_m = re.search(r"<args>(?P<args>[\s\S]*?)</args>", body, re.IGNORECASE)
        args_raw = str(args_m.group("args") if args_m else "").strip()
        args = _parse_args_xmlish(args_raw)

        tool_calls.append(
            {
                "id": "call_" + uuid.uuid4().hex,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            }
        )

    # Some prompts wrap everything with a FUNC_TRIGGER_* marker.
    # If we saw it but couldn't parse anything, treat as "no tool calls".
    return tool_calls


def extract_openai_tool_calls(response_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(response_payload, dict):
        return []
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    first = choices[0]
    if not isinstance(first, dict):
        return []
    message = first.get("message")
    if not isinstance(message, dict):
        return []
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        return [tc for tc in tool_calls if isinstance(tc, dict)]
    # Legacy `function_call`
    function_call = message.get("function_call")
    if isinstance(function_call, dict) and function_call.get("name"):
        return [
            {
                "id": "call_" + uuid.uuid4().hex,
                "type": "function",
                "function": {
                    "name": function_call.get("name"),
                    "arguments": function_call.get("arguments") or "{}",
                },
            }
        ]

    # Fallback: tool calls embedded in the text content (tagged format).
    content_text = _extract_text_from_content_field(message.get("content"))
    if not content_text:
        raw_text = first.get("text")
        if isinstance(raw_text, str) and raw_text.strip():
            content_text = raw_text
    if content_text:
        # Strip FUNC_TRIGGER prefix for better matching, but keep the remaining tags.
        sanitized = _FUNC_TRIGGER_RE.sub("", content_text)
        parsed = _extract_tool_calls_from_tagged_text(sanitized)
        if parsed:
            return parsed
    return []


def tool_call_to_args(tool_call: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    tool_call_id = str(tool_call.get("id") or "").strip() or None
    fn = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
    name = str(fn.get("name") or "").strip()
    raw_args = fn.get("arguments")
    args: dict[str, Any] = {}
    if isinstance(raw_args, str) and raw_args.strip():
        parsed = _safe_json_loads(raw_args)
        if isinstance(parsed, dict):
            args = parsed
    elif isinstance(raw_args, dict):
        args = raw_args
    return name, args, tool_call_id


async def wait_for_bridge_result(
    *,
    gateway: BridgeGatewayClient,
    req_id: str,
    timeout_seconds: float,
) -> BridgeToolResult:
    start = time.time()
    async for msg in iter_sse_events(gateway.stream_events()):
        if time.time() - start > timeout_seconds:
            break
        if msg.event != "bridge":
            continue
        try:
            env = json.loads(msg.data)
        except Exception:
            continue
        if not isinstance(env, dict):
            continue
        if str(env.get("type") or "").strip() != "RESULT":
            continue
        if str(env.get("req_id") or "").strip() != req_id:
            continue
        payload = env.get("payload") if isinstance(env.get("payload"), dict) else {}
        return BridgeToolResult(
            ok=bool(payload.get("ok", False)),
            exit_code=int(payload.get("exit_code") or 0),
            canceled=bool(payload.get("canceled", False)),
            result_json=payload.get("result_json"),
            error=payload.get("error") if isinstance(payload.get("error"), dict) else None,
        )
    return BridgeToolResult(
        ok=False,
        exit_code=0,
        canceled=False,
        result_json=None,
        error={"code": "invoke_timeout", "message": "bridge tool result timeout"},
    )


async def invoke_bridge_tool_and_wait(
    *,
    base_url: str | None = None,
    internal_token: str | None = None,
    req_id: str,
    agent_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_ms: int,
    result_timeout_seconds: float = 120.0,
) -> BridgeToolResult:
    """
    Invoke a tool via Gateway and wait for its RESULT via the Gateway SSE stream.

    注意：该实现是 MVP 版本（单连接共享 SSE），用于打通闭环；
    后续多实例/高并发场景应迁移到 reply_to / Redis Streams / result KV 等更可靠的回传机制。
    """
    gateway = BridgeGatewayClient(base_url=base_url, internal_token=internal_token, timeout=30.0)

    # Fire invoke
    try:
        await gateway.invoke(
            req_id=req_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            timeout_ms=timeout_ms,
            stream=True,
        )
    except httpx.HTTPStatusError as exc:
        status = int(getattr(exc.response, "status_code", 500) or 500)
        err_text = ""
        err_code = "invoke_failed"
        try:
            payload = exc.response.json()
            if isinstance(payload, dict) and isinstance(payload.get("error"), str) and payload["error"].strip():
                err_code = payload["error"].strip()
        except Exception:
            payload = None
        try:
            err_text = exc.response.text
        except Exception:
            err_text = ""
        return BridgeToolResult(
            ok=False,
            exit_code=0,
            canceled=False,
            result_json=None,
            error={"code": err_code, "message": f"invoke failed ({status}): {err_text}"},
        )
    except Exception as exc:  # pragma: no cover
        return BridgeToolResult(
            ok=False,
            exit_code=0,
            canceled=False,
            result_json=None,
            error={"code": "invoke_failed", "message": str(exc)},
        )

    return await wait_for_bridge_result(gateway=gateway, req_id=req_id, timeout_seconds=result_timeout_seconds)
