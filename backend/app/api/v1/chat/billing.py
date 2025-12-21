"""
计费相关逻辑封装
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

from app.logging_config import logger
from app.services.credit_service import (
    record_chat_completion_usage as _record_chat_completion_usage,
)
from app.services.credit_service import (
    record_streaming_request as _record_streaming_request,
)


def _compact_request_hint(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Celery 任务只需要少量字段用于估算 token，避免把完整请求体丢进 broker。
    """
    if not isinstance(payload, dict):
        return None
    keys = (
        "model",
        "max_tokens",
        "max_tokens_to_sample",
        "max_output_tokens",
    )
    hint: dict[str, Any] = {k: payload.get(k) for k in keys if k in payload}
    return hint or None


def _extract_usage(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def _enqueue_celery_task(task_name: str, *, kwargs: dict[str, Any]) -> None:
    """
    将 send_task 放到线程里异步执行，避免 broker 连接抖动阻塞 API 响应时间。
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        return

    from app.celery_app import celery_app

    def _send() -> None:
        celery_app.send_task(task_name, kwargs=kwargs, ignore_result=True)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 没有事件循环（极少数同步上下文）：直接发送（可能阻塞）。
        try:
            _send()
        except Exception:
            logger.warning("Failed to enqueue celery task=%s", task_name, exc_info=True)
        return

    async def _dispatch() -> None:
        try:
            await asyncio.to_thread(_send)
        except Exception:
            logger.warning("Failed to enqueue celery task=%s", task_name, exc_info=True)

    asyncio.create_task(_dispatch())


def record_completion_usage(
    db: DbSession,
    *,
    user_id: UUID,
    api_key_id: UUID,
    logical_model_name: str,
    provider_id: str | None,
    provider_model_id: str | None,
    response_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
    is_stream: bool = False,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """
    记录聊天完成的积分消耗（非流式）
    
    封装异常处理，避免计费失败影响主流程
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        try:
            occurred_at = dt.datetime.now(tz=dt.UTC)
            _record_chat_completion_usage(
                db,
                user_id=user_id,
                api_key_id=api_key_id,
                logical_model_name=logical_model_name,
                provider_id=provider_id,
                provider_model_id=provider_model_id,
                response_payload=response_payload,
                request_payload=request_payload,
                is_stream=is_stream,
                reason=reason,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
            )
        except Exception:
            logger.exception(
                "Failed to record credit usage for chat completion "
                "(user=%s logical_model=%s provider=%s)",
                user_id,
                logical_model_name,
                provider_id,
            )
        return

    occurred_at = dt.datetime.now(tz=dt.UTC).isoformat()
    _enqueue_celery_task(
        "tasks.credits.record_chat_completion_usage",
        kwargs={
            "user_id": str(user_id),
            "api_key_id": str(api_key_id) if api_key_id else None,
            "logical_model_name": logical_model_name,
            "provider_id": provider_id,
            "provider_model_id": provider_model_id,
            "usage": _extract_usage(response_payload),
            "request_hint": _compact_request_hint(request_payload),
            "is_stream": bool(is_stream),
            "reason": reason,
            "idempotency_key": idempotency_key,
            "occurred_at": occurred_at,
        },
    )


def record_stream_usage(
    db: DbSession,
    *,
    user_id: UUID,
    api_key_id: UUID,
    logical_model_name: str,
    provider_id: str | None,
    provider_model_id: str | None,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
) -> None:
    """
    记录流式请求的积分预扣（基于请求参数估算）
    
    封装异常处理，避免计费失败影响主流程
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        try:
            _record_streaming_request(
                db,
                user_id=user_id,
                api_key_id=api_key_id,
                logical_model_name=logical_model_name,
                provider_id=provider_id,
                provider_model_id=provider_model_id,
                payload=payload,
                idempotency_key=idempotency_key,
            )
        except Exception:
            logger.exception(
                "Failed to record streaming credit usage "
                "(user=%s logical_model=%s provider=%s)",
                user_id,
                logical_model_name,
                provider_id,
            )
        return

    _enqueue_celery_task(
        "tasks.credits.record_streaming_request",
        kwargs={
            "user_id": str(user_id),
            "api_key_id": str(api_key_id) if api_key_id else None,
            "logical_model_name": logical_model_name,
            "provider_id": provider_id,
            "provider_model_id": provider_model_id,
            "request_hint": _compact_request_hint(payload) or {},
            "idempotency_key": idempotency_key,
        },
    )
