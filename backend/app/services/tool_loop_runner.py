from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.logging_config import logger
from app.services.bridge_tool_runner import (
    BridgeToolResult,
    extract_openai_tool_calls,
    tool_call_to_args,
)


RunEventSink = Callable[[str, dict[str, Any]], None]
InvokeTool = Callable[[str, str, str, dict[str, Any]], Awaitable[BridgeToolResult]]
CancelTool = Callable[[str, str, str], Awaitable[None]]
CallModel = Callable[[dict[str, Any], str], Awaitable[dict[str, Any] | None]]


@dataclass(frozen=True)
class ToolLoopLimits:
    max_rounds: int = 4
    max_invocations: int = 12
    max_total_duration_ms: int = 5 * 60 * 1000
    model_call_timeout_ms: int = 120 * 1000


@dataclass(frozen=True)
class ToolLoopResult:
    first_response_payload: dict[str, Any] | None
    final_response_payload: dict[str, Any] | None
    tool_invocations: list[dict[str, Any]]
    output_text: str | None
    error_code: str | None
    error_message: str | None
    did_run: bool


class ToolLoopRunner:
    def __init__(
        self,
        *,
        invoke_tool: InvokeTool,
        call_model: CallModel,
        cancel_tool: CancelTool | None = None,
        event_sink: RunEventSink | None = None,
        limits: ToolLoopLimits | None = None,
    ) -> None:
        self._invoke_tool = invoke_tool
        self._call_model = call_model
        self._cancel_tool = cancel_tool
        self._event_sink = event_sink
        self._limits = limits or ToolLoopLimits()

    async def run(
        self,
        *,
        conversation_id: str,
        run_id: str,
        base_payload: dict[str, Any],
        first_response_payload: dict[str, Any] | None,
        effective_bridge_agent_ids: list[str],
        tool_name_map: dict[str, tuple[str, str]],
        assistant_message_id: str | None = None,
        user_message_id: str | None = None,
        idempotency_prefix: str | None = None,
    ) -> ToolLoopResult:
        started_at = time.perf_counter()
        current_payload = dict(base_payload)
        current_response = first_response_payload
        round_idx = 0
        invocation_records: list[dict[str, Any]] = []

        def emit(event_type: str, payload: dict[str, Any]) -> None:
            if self._event_sink is None:
                return
            try:
                self._event_sink(event_type, payload)
            except Exception:
                return

        while True:
            elapsed_ms = int(max(0, (time.perf_counter() - started_at) * 1000))
            if elapsed_ms > self._limits.max_total_duration_ms:
                return ToolLoopResult(
                    first_response_payload=first_response_payload,
                    final_response_payload=current_response,
                    tool_invocations=invocation_records,
                    output_text=None,
                    error_code="TOOL_LOOP_TIMEOUT",
                    error_message="tool loop exceeded max_total_duration_ms",
                    did_run=bool(invocation_records),
                )

            if round_idx >= self._limits.max_rounds:
                return ToolLoopResult(
                    first_response_payload=first_response_payload,
                    final_response_payload=current_response,
                    tool_invocations=invocation_records,
                    output_text=None,
                    error_code="TOOL_LOOP_MAX_ROUNDS",
                    error_message="tool loop exceeded max_rounds",
                    did_run=bool(invocation_records),
                )

            tool_calls = extract_openai_tool_calls(current_response)
            if not tool_calls:
                return ToolLoopResult(
                    first_response_payload=first_response_payload,
                    final_response_payload=current_response,
                    tool_invocations=invocation_records,
                    output_text=_extract_first_choice_text(current_response),
                    error_code=None,
                    error_message=None,
                    did_run=bool(invocation_records),
                )

            tool_messages: list[dict[str, Any]] = []
            for tc in tool_calls:
                if len(invocation_records) >= self._limits.max_invocations:
                    return ToolLoopResult(
                        first_response_payload=first_response_payload,
                        final_response_payload=current_response,
                        tool_invocations=invocation_records,
                        output_text=None,
                        error_code="TOOL_LOOP_MAX_INVOCATIONS",
                        error_message="tool loop exceeded max_invocations",
                        did_run=True,
                    )

                model_tool_name, args, tool_call_id = tool_call_to_args(tc)
                if not model_tool_name:
                    continue

                mapped = tool_name_map.get(model_tool_name)
                if mapped:
                    target_agent_id, target_tool_name = mapped
                else:
                    target_agent_id = effective_bridge_agent_ids[0] if effective_bridge_agent_ids else ""
                    target_tool_name = model_tool_name
                if not target_agent_id or not target_tool_name:
                    continue

                req_id = "req_" + uuid.uuid4().hex
                emit(
                    "tool.status",
                    {
                        "type": "tool.status",
                        "conversation_id": conversation_id,
                        "run_id": run_id,
                        "user_message_id": user_message_id,
                        "assistant_message_id": assistant_message_id,
                        "req_id": req_id,
                        "agent_id": target_agent_id,
                        "tool_name": target_tool_name,
                        "tool_call_id": tool_call_id,
                        "state": "running",
                    },
                )

                t_tool = time.perf_counter()
                tool_result = await self._invoke_tool(req_id, target_agent_id, target_tool_name, args)
                duration_ms = int(max(0, (time.perf_counter() - t_tool) * 1000))

                error_code = None
                if isinstance(tool_result.error, dict):
                    error_code = str(tool_result.error.get("code") or "").strip() or None

                if tool_result.ok:
                    state = "done"
                elif tool_result.canceled:
                    state = "canceled"
                elif error_code == "invoke_timeout":
                    state = "timeout"
                else:
                    state = "failed"

                result_preview = None
                try:
                    if tool_result.result_json is not None:
                        result_preview = json.dumps(tool_result.result_json, ensure_ascii=False)[:800]
                    elif isinstance(tool_result.error, dict):
                        result_preview = (
                            str(tool_result.error.get("message") or tool_result.error.get("code") or "")[:800] or None
                        )
                except Exception:
                    result_preview = None

                if state == "timeout" and self._cancel_tool is not None:
                    try:
                        await self._cancel_tool(req_id, target_agent_id, "invoke_timeout")
                    except Exception:
                        pass

                record: dict[str, Any] = {
                    "req_id": req_id,
                    "agent_id": target_agent_id,
                    "tool_name": target_tool_name,
                    "tool_call_id": tool_call_id,
                    "state": state,
                    "duration_ms": duration_ms,
                    "ok": bool(tool_result.ok),
                    "canceled": bool(tool_result.canceled),
                    "exit_code": int(tool_result.exit_code or 0),
                    "error": tool_result.error,
                    "result_preview": result_preview,
                }
                invocation_records.append(record)
                emit(
                    "tool.result",
                    {
                        "type": "tool.result",
                        "conversation_id": conversation_id,
                        "run_id": run_id,
                        "user_message_id": user_message_id,
                        "assistant_message_id": assistant_message_id,
                        **record,
                    },
                )

                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id or req_id,
                        "content": json.dumps(
                            {
                                "req_id": req_id,
                                "agent_id": target_agent_id,
                                "tool_name": target_tool_name,
                                "model_tool_name": model_tool_name,
                                "ok": tool_result.ok,
                                "exit_code": tool_result.exit_code,
                                "canceled": tool_result.canceled,
                                "result_json": tool_result.result_json,
                                "error": tool_result.error,
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

            if not tool_messages:
                return ToolLoopResult(
                    first_response_payload=first_response_payload,
                    final_response_payload=current_response,
                    tool_invocations=invocation_records,
                    output_text=_extract_first_choice_text(current_response),
                    error_code=None,
                    error_message=None,
                    did_run=bool(invocation_records),
                )

            follow_payload = dict(current_payload)
            follow_messages = list(current_payload.get("messages") or [])
            follow_messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
            follow_messages.extend(tool_messages)
            follow_payload["messages"] = follow_messages
            follow_payload["tool_choice"] = "auto"
            # Tool loop 的 follow-up 必须使用非流式调用：
            # - 避免 payload 继承了 baseline 的 stream=True，导致上游返回 SSE 文本而不是 JSON；
            # - 避免在 worker 内部发起流式请求但无人消费，造成请求悬挂/超时。
            follow_payload["stream"] = False

            idempotency_key = None
            if idempotency_prefix:
                idempotency_key = f"{idempotency_prefix}:{round_idx}"

            elapsed_ms = int(max(0, (time.perf_counter() - started_at) * 1000))
            remaining_ms = int(max(0, self._limits.max_total_duration_ms - elapsed_ms))
            timeout_ms = int(min(remaining_ms, int(self._limits.model_call_timeout_ms or 0)))
            if timeout_ms <= 0:
                return ToolLoopResult(
                    first_response_payload=first_response_payload,
                    final_response_payload=current_response,
                    tool_invocations=invocation_records,
                    output_text=None,
                    error_code="TOOL_LOOP_TIMEOUT",
                    error_message="tool loop exceeded max_total_duration_ms",
                    did_run=bool(invocation_records),
                )

            try:
                logger.info(
                    "tool_loop: model follow-up start run_id=%s round=%d timeout_ms=%d",
                    run_id,
                    round_idx,
                    timeout_ms,
                )
                current_response = await asyncio.wait_for(
                    self._call_model(follow_payload, idempotency_key or ""),
                    timeout=float(timeout_ms) / 1000.0,
                )
                logger.info(
                    "tool_loop: model follow-up done run_id=%s round=%d has_response=%s",
                    run_id,
                    round_idx,
                    bool(current_response),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "tool_loop: model follow-up timeout run_id=%s round=%d timeout_ms=%d",
                    run_id,
                    round_idx,
                    timeout_ms,
                )
                return ToolLoopResult(
                    first_response_payload=first_response_payload,
                    final_response_payload=current_response,
                    tool_invocations=invocation_records,
                    output_text=None,
                    error_code="TOOL_LOOP_MODEL_TIMEOUT",
                    error_message="tool loop model follow-up timed out",
                    did_run=bool(invocation_records),
                )
            current_payload = follow_payload
            round_idx += 1


def _extract_first_choice_text(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, str) and part:
                    text_parts.append(part)
                    continue
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
                    continue
                if isinstance(text, dict):
                    value = text.get("value")
                    if isinstance(value, str) and value:
                        text_parts.append(value)
            combined = "".join(text_parts).strip()
            if combined:
                return combined
    content = first.get("text")
    if isinstance(content, str) and content.strip():
        return content
    return None


def split_text_into_deltas(
    text: str,
    *,
    target_chunk_chars: int = 24,
    max_chunks: int = 240,
) -> list[str]:
    """
    将完整文本拆分为多个较小的 delta 片段，用于模拟“逐字流式”体验。

    约束：
    - 不依赖任何外部配置，避免引入新的环境变量/配置键
    - 尽量控制片段数量，避免 Redis/SSE 事件过多
    """
    value = str(text or "")
    if not value:
        return []

    chunk_chars = max(1, int(target_chunk_chars))
    limit = max(1, int(max_chunks))

    # 若文本很长，自动放大 chunk size，保证 chunks 数量不超过 limit。
    if len(value) > chunk_chars * limit:
        chunk_chars = max(chunk_chars, int(math.ceil(len(value) / limit)))

    return [value[i : i + chunk_chars] for i in range(0, len(value), chunk_chars)]


__all__ = [
    "CallModel",
    "CancelTool",
    "InvokeTool",
    "RunEventSink",
    "ToolLoopLimits",
    "ToolLoopResult",
    "ToolLoopRunner",
    "split_text_into_deltas",
]
