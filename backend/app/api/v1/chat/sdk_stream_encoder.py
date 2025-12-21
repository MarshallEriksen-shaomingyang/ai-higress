"""
SDK 流式输出编码器（v2）

SDK driver 的 stream_content 统一产出 dict，而网关对外主要输出 SSE bytes。
本模块负责把不同 SDK 的 dict chunk 统一编码为：
- OpenAI chat.completions SSE（data: {...}\\n\\n）
- Claude messages SSE（event: ...\\ndata: {...}\\n\\n）
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any


def encode_openai_sse_event(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def encode_openai_done() -> bytes:
    return b"data: [DONE]\n\n"


def encode_claude_sse_event(event_name: str, payload: dict[str, Any]) -> bytes:
    name = (event_name or "message_delta").strip()
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {name}\ndata: {data}\n\n".encode()


class GeminiDictToOpenAISSEAdapter:
    """
    将 google-genai streaming 的 dict 分片转换为 OpenAI chat.completions SSE。

    约定：
    - 尽量提取 candidates[0].content.parts 中的 text，作为 delta content。
    - 不保证覆盖所有 Gemini 事件形态（例如工具调用），但保证基本文本流式可用。
    """

    def __init__(self, model: str | None) -> None:
        self.model = model
        self.response_id = f"chatcmpl-{uuid.uuid4().hex}"
        self.created = int(time.time())
        self.done = False

    def _extract_text_delta(self, chunk: dict[str, Any]) -> str:
        candidates = chunk.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ""
        first = candidates[0]
        if not isinstance(first, dict):
            return ""
        content = first.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                texts.append(text)
        return "".join(texts)

    def process_chunk(self, chunk: dict[str, Any]) -> list[bytes]:
        if self.done:
            return []
        text = self._extract_text_delta(chunk)
        if not text:
            return []
        payload = {
            "id": self.response_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
        }
        return [encode_openai_sse_event(payload)]

    def finalize(self) -> list[bytes]:
        if self.done:
            return []
        self.done = True
        tail = {
            "id": self.response_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        return [encode_openai_sse_event(tail), encode_openai_done()]


def encode_openai_sdk_chunk_dict(chunk: dict[str, Any]) -> bytes:
    """
    OpenAI SDK stream_content 返回的是 dict chunk；对外编码为 SSE data 行。
    """
    return encode_openai_sse_event(chunk)


def encode_claude_sdk_event_dict(chunk: dict[str, Any]) -> bytes:
    """
    Anthropic SDK stream_content 返回的是事件 dict；对外编码为 Claude SSE。
    """
    event_name = chunk.get("type")
    if not isinstance(event_name, str) or not event_name.strip():
        event_name = "message_delta"
    return encode_claude_sse_event(event_name, chunk)


__all__ = [
    "GeminiDictToOpenAISSEAdapter",
    "encode_claude_sdk_event_dict",
    "encode_openai_done",
    "encode_openai_sdk_chunk_dict",
]

