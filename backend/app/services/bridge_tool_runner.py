from __future__ import annotations

import hashlib
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
