"""
Celery 任务：聊天计费（异步扣费/流水写入）。

说明：
- 任务内部自行创建 DB Session，避免在 Web 进程中做同步扣费阻塞响应；
- 使用 CreditTransaction.idempotency_key 做幂等去重，避免任务重试/重复投递导致重复扣费。
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from uuid import UUID

from celery import shared_task

from app.db import SessionLocal
from app.logging_config import logger
from app.services.credit_service import record_chat_completion_usage, record_streaming_request


def _to_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    return UUID(value)

def _to_datetime(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


@shared_task(name="tasks.credits.record_chat_completion_usage")
def record_chat_completion_usage_task(
    *,
    user_id: str,
    api_key_id: str | None,
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    usage: dict[str, Any] | None,
    request_hint: dict[str, Any] | None,
    is_stream: bool = False,
    reason: str | None = None,
    idempotency_key: str | None = None,
    occurred_at: str | None = None,
) -> int:
    session = SessionLocal()
    try:
        return record_chat_completion_usage(
            session,
            user_id=UUID(user_id),
            api_key_id=_to_uuid(api_key_id),
            logical_model_name=logical_model_name,
            provider_id=provider_id,
            provider_model_id=provider_model_id,
            response_payload={"usage": usage} if isinstance(usage, dict) else None,
            request_payload=request_hint if isinstance(request_hint, dict) else None,
            is_stream=is_stream,
            reason=reason,
            idempotency_key=idempotency_key,
            occurred_at=_to_datetime(occurred_at),
        )
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Async credit billing failed: user=%s model=%s provider=%s",
            user_id,
            logical_model_name,
            provider_id,
        )
        return 0
    finally:
        session.close()


@shared_task(name="tasks.credits.record_streaming_request")
def record_streaming_request_task(
    *,
    user_id: str,
    api_key_id: str | None,
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    request_hint: dict[str, Any],
    idempotency_key: str | None = None,
) -> int:
    session = SessionLocal()
    try:
        return record_streaming_request(
            session,
            user_id=UUID(user_id),
            api_key_id=_to_uuid(api_key_id),
            logical_model_name=logical_model_name,
            provider_id=provider_id,
            provider_model_id=provider_model_id,
            payload=request_hint if isinstance(request_hint, dict) else {},
            idempotency_key=idempotency_key,
        )
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Async streaming precharge failed: user=%s model=%s provider=%s",
            user_id,
            logical_model_name,
            provider_id,
        )
        return 0
    finally:
        session.close()


__all__ = ["record_chat_completion_usage_task", "record_streaming_request_task"]
