"""
流式协议转换层（v2）

约定：
- 输入/输出均为 bytes 迭代器（通常是 SSE/event-stream 数据）。
- 用于在「上游实际 api_style」与「客户端期望 api_style」不一致时做转换。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal, cast

from fastapi.responses import StreamingResponse

from app.services.chat_routing_service import OpenAIToClaudeStreamAdapter, _wrap_chat_stream_response

ApiStyle = Literal["openai", "claude", "responses"]


def _as_style(value: str | None) -> ApiStyle:
    v = str(value or "").strip().lower()
    if v in ("openai", "claude", "responses"):
        return cast(ApiStyle, v)
    return "openai"


class ClaudeToOpenAIStreamAdapter:
    """
    将 Claude messages SSE（event: content_block_delta 等）转换为 OpenAI chat.completions SSE。

    这里只做“文本增量”的最小兼容转换，满足大多数客户端消费。
    """

    def __init__(self, model: str | None) -> None:
        self.model = model
        self.buffer = ""
        self.started = False
        self.sent_role = False
        self.finish_reason: str | None = None
        self.had_error = False

    def _encode_openai(self, payload: dict[str, Any]) -> bytes:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()

    def _emit_role_once(self) -> list[bytes]:
        if self.sent_role:
            return []
        self.sent_role = True
        payload = {
            "id": None,
            "object": "chat.completion.chunk",
            "model": self.model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        return [self._encode_openai(payload)]

    def process_chunk(self, chunk: bytes) -> list[bytes]:
        outputs: list[bytes] = []
        try:
            decoded = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return outputs
        if self.had_error:
            return outputs
        self.buffer += decoded

        while "\n\n" in self.buffer:
            raw_event, self.buffer = self.buffer.split("\n\n", 1)
            raw_event = raw_event.strip()
            if not raw_event:
                continue

            event_type: str | None = None
            data_lines: list[str] = []
            for line in raw_event.splitlines():
                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())

            if not data_lines:
                continue
            data_str = "\n".join(data_lines).strip()
            if not data_str:
                continue

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if event_type == "error":
                message = "Upstream streaming error"
                if isinstance(data, dict):
                    err = data.get("error")
                    if isinstance(err, dict):
                        raw_message = err.get("message")
                        if isinstance(raw_message, str) and raw_message.strip():
                            message = raw_message.strip()
                        else:
                            message = json.dumps(err, ensure_ascii=False)
                    elif isinstance(err, str) and err.strip():
                        message = err.strip()
                if not self.started:
                    self.started = True
                    outputs.extend(self._emit_role_once())
                outputs.append(
                    self._encode_openai(
                        {
                            "id": None,
                            "object": "chat.completion.chunk",
                            "model": self.model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": message},
                                    "finish_reason": "stop",
                                }
                            ],
                            "error": {
                                "type": "upstream_error",
                                "message": message,
                            },
                        }
                    )
                )
                outputs.append(b"data: [DONE]\n\n")
                self.had_error = True
                continue

            if event_type == "content_block_delta":
                delta = data.get("delta") if isinstance(data, dict) else None
                if isinstance(delta, dict) and delta.get("type") == "text_delta":
                    text = delta.get("text")
                    if isinstance(text, str) and text:
                        if not self.started:
                            self.started = True
                            outputs.extend(self._emit_role_once())
                        outputs.append(
                            self._encode_openai(
                                {
                                    "id": None,
                                    "object": "chat.completion.chunk",
                                    "model": self.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": text},
                                            "finish_reason": None,
                                        }
                                    ],
                                }
                            )
                        )
            elif event_type == "message_delta":
                delta = data.get("delta") if isinstance(data, dict) else None
                if isinstance(delta, dict) and isinstance(delta.get("stop_reason"), str):
                    stop_reason = delta["stop_reason"]
                    self.finish_reason = {
                        "end_turn": "stop",
                        "max_tokens": "length",
                    }.get(stop_reason, "stop")
            elif event_type == "message_stop":
                if not self.started:
                    self.started = True
                    outputs.extend(self._emit_role_once())
                outputs.append(
                    self._encode_openai(
                        {
                            "id": None,
                            "object": "chat.completion.chunk",
                            "model": self.model,
                            "choices": [
                                {"index": 0, "delta": {}, "finish_reason": self.finish_reason or "stop"}
                            ],
                        }
                    )
                )
                outputs.append(b"data: [DONE]\n\n")
        return outputs


async def _convert_claude_sse_to_openai_sse(
    iterator: AsyncIterator[bytes],
    *,
    model: str | None,
) -> AsyncIterator[bytes]:
    adapter = ClaudeToOpenAIStreamAdapter(model)
    async for chunk in iterator:
        for out in adapter.process_chunk(chunk):
            yield out


async def _convert_openai_sse_to_claude_sse(
    iterator: AsyncIterator[bytes],
    *,
    model: str | None,
) -> AsyncIterator[bytes]:
    adapter = OpenAIToClaudeStreamAdapter(model)
    async for chunk in iterator:
        for out in adapter.process_chunk(chunk):
            yield out
    for tail in adapter.finalize():
        yield tail


async def adapt_stream(
    iterator: AsyncIterator[bytes],
    *,
    from_style: str,
    to_style: str,
    request_model: str | None,
) -> AsyncIterator[bytes]:
    """
    将流式输出从 from_style 转换为 to_style。
    """
    source_style = _as_style(from_style)
    target_style = _as_style(to_style)

    if source_style == target_style:
        async for chunk in iterator:
            yield chunk
        return

    model = request_model

    if source_style == "openai":
        if target_style == "claude":
            async for out in _convert_openai_sse_to_claude_sse(iterator, model=model):
                yield out
            return
        if target_style == "responses":
            openai_resp = StreamingResponse(iterator, media_type="text/event-stream")
            converted = _wrap_chat_stream_response(openai_resp)
            async for out in converted.body_iterator:
                yield out
            return
        raise ValueError("Unsupported stream conversion from openai")

    if source_style == "claude":
        if target_style == "openai":
            async for out in _convert_claude_sse_to_openai_sse(iterator, model=model):
                yield out
            return
        if target_style == "responses":
            async def _openai_iter() -> AsyncIterator[bytes]:
                async for out in _convert_claude_sse_to_openai_sse(iterator, model=model):
                    yield out

            openai_resp = StreamingResponse(_openai_iter(), media_type="text/event-stream")
            converted = _wrap_chat_stream_response(openai_resp)
            async for out in converted.body_iterator:
                yield out
            return
        raise ValueError("Unsupported stream conversion from claude")

    raise ValueError("Unsupported stream conversion from responses")


__all__ = ["ClaudeToOpenAIStreamAdapter", "adapt_stream"]
