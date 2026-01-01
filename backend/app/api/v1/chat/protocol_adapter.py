"""
协议转换层（v2）

设计目标：
- 让 transport 只负责「发送/接收/metrics/错误分类」，不再承担跨 API 风格的转换分支。
- 将客户端请求/响应的 api_style（openai/claude/responses）与上游实际 api_style 解耦，
  通过统一的 adapter 在两者之间做显式转换。
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from app.services.chat_routing_service import (
    _adapt_responses_payload,
    _chat_to_responses_payload,
    _claude_messages_to_openai_chat_payload,
    _openai_chat_to_claude_response,
)
from app.services.claude_cli_transformer import transform_claude_response_to_openai

ApiStyle = Literal["openai", "claude", "responses"]


def _as_style(value: str | None) -> ApiStyle:
    v = str(value or "").strip().lower()
    if v in ("openai", "claude", "responses"):
        return cast(ApiStyle, v)
    return "openai"


def _ensure_json_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _openai_chat_to_claude_messages_payload(
    chat_payload: dict[str, Any],
    *,
    upstream_model_id: str,
) -> dict[str, Any]:
    """
    将 OpenAI chat.completions 风格请求转换为 Claude messages 请求。

    说明：
    - 只保证文本/基础参数/工具定义的常用字段映射；
    - 不可映射或语义差异较大的字段，默认尽量忽略而不是伪造。
    """
    payload = dict(chat_payload)
    payload["model"] = upstream_model_id

    # Extract system messages into `system` (Anthropic supports string or list).
    system_texts: list[str] = []
    messages: list[dict[str, Any]] = []
    for msg in payload.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or "user"
        content = msg.get("content")
        # OpenAI tool result -> Claude tool_result block（放在 user 消息里）
        if role == "tool":
            tool_call_id = str(msg.get("tool_call_id") or "").strip() or None
            text_content = ""
            if isinstance(content, str):
                text_content = content
            elif isinstance(content, dict):
                text_content = json.dumps(content, ensure_ascii=False)
            elif content is not None:
                text_content = str(content)

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id or "unknown",
                            "content": [{"type": "text", "text": text_content}],
                        }
                    ],
                }
            )
            continue

        if role == "system":
            if isinstance(content, str) and content.strip():
                system_texts.append(content)
            elif isinstance(content, list):
                # OpenAI multimodal segments: keep text segments only.
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        system_texts.append(item["text"])
            continue

        # Claude requires content blocks array.
        if isinstance(content, str):
            claude_content: Any = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            blocks: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    blocks.append({"type": "text", "text": item["text"]})
                elif isinstance(item.get("text"), str):
                    blocks.append({"type": "text", "text": item["text"]})
            claude_content = blocks
        else:
            claude_content = [{"type": "text", "text": str(content)}]

        messages.append({"role": role, "content": claude_content})

    payload["messages"] = messages or [{"role": "user", "content": [{"type": "text", "text": ""}]}]

    if system_texts:
        joined = "\n".join(text for text in system_texts if text)
        payload["system"] = [{"type": "text", "text": joined}]
    else:
        payload.pop("system", None)

    # Tools mapping: OpenAI -> Claude input_schema
    tools = payload.get("tools")
    if isinstance(tools, list) and tools:
        converted_tools: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if tool.get("type") != "function":
                continue
            fn = tool.get("function")
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            parameters = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {"type": "object", "properties": {}}
            converted_tools.append(
                {
                    "name": name,
                    "description": fn.get("description") or "",
                    "input_schema": parameters,
                }
            )
        if converted_tools:
            payload["tools"] = converted_tools

    # OpenAI max_tokens -> Claude max_tokens (兼容 max_tokens_to_sample)
    if payload.get("max_tokens") is None and payload.get("max_tokens_to_sample") is not None:
        payload["max_tokens"] = payload.get("max_tokens_to_sample")
    payload.pop("max_tokens_to_sample", None)

    # Claude expects stop_sequences
    if payload.get("stop_sequences") is None and payload.get("stop") is not None:
        payload["stop_sequences"] = payload.get("stop")
    payload.pop("stop", None)

    return payload


def adapt_request_payload(
    payload: dict[str, Any],
    *,
    from_style: str,
    to_style: str,
    upstream_model_id: str,
) -> dict[str, Any]:
    """
    将客户端请求 payload 从 from_style 转换为上游 to_style 可接受的请求 payload。
    """
    source_style = _as_style(from_style)
    target_style = _as_style(to_style)

    if source_style == target_style:
        copied = json.loads(json.dumps(payload, ensure_ascii=False))
        copied["model"] = upstream_model_id
        return copied

    # First: normalize into OpenAI chat payload as internal canonical request.
    if source_style == "openai":
        chat_payload = dict(payload)
    elif source_style == "responses":
        chat_payload = _adapt_responses_payload(payload)
    else:  # claude
        chat_payload = _claude_messages_to_openai_chat_payload(
            payload, upstream_model_id=upstream_model_id
        )

    # Ensure upstream model id is applied in canonical form.
    chat_payload["model"] = upstream_model_id

    if target_style == "openai":
        return chat_payload

    if target_style == "claude":
        return _openai_chat_to_claude_messages_payload(
            chat_payload,
            upstream_model_id=upstream_model_id,
        )

    # target_style == "responses"
    if source_style != "responses":
        # 当前实现刻意不支持「openai/claude -> responses 请求」以避免生成不符合语义的 payload。
        raise ValueError("Unsupported request conversion to responses")
    copied = dict(payload)
    copied["model"] = upstream_model_id
    return copied


def adapt_response_payload(
    payload: Any,
    *,
    from_style: str,
    to_style: str,
    request_model: str | None,
) -> Any:
    """
    将上游响应从 from_style 转换为客户端 to_style。

    - 返回值保持 JSON 结构（dict/list/primitive），由上层决定如何封装为 Response。
    """
    source_style = _as_style(from_style)
    target_style = _as_style(to_style)

    if source_style == target_style:
        return payload

    src_dict = _ensure_json_dict(payload)
    if src_dict is None:
        return payload

    # Normalize into OpenAI chat response as internal canonical response.
    if source_style == "openai":
        chat_payload = src_dict
    elif source_style == "claude":
        chat_payload = transform_claude_response_to_openai(
            src_dict,
            original_model=request_model or "",
        )
    else:
        raise ValueError("Unsupported response conversion from responses")

    if target_style == "openai":
        return chat_payload

    if target_style == "claude":
        return _openai_chat_to_claude_response(
            chat_payload,
            request_model=request_model,
        )

    # target_style == "responses"
    return _chat_to_responses_payload(chat_payload)


def stringify_payload(value: Any) -> str:
    """
    Best-effort stringify for context/audit storage.
    """
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


__all__ = [
    "ApiStyle",
    "adapt_request_payload",
    "adapt_response_payload",
    "stringify_payload",
]
