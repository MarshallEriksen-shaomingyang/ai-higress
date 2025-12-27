from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.user_app_metrics_repository import (
    record_user_app_request_metric as repo_record_user_app_request_metric,
)


def _current_bucket_start(now: dt.datetime, bucket_seconds: int) -> dt.datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.UTC)
    else:
        now = now.astimezone(dt.UTC)

    epoch_seconds = int(now.timestamp())
    bucket_start = epoch_seconds - (epoch_seconds % bucket_seconds)
    return dt.datetime.fromtimestamp(bucket_start, tz=dt.UTC)


def record_user_app_request_metric(
    db: Session,
    *,
    user_id: UUID,
    api_key_id: UUID | None,
    app_name: str,
    occurred_at: dt.datetime | None = None,
    bucket_seconds: int = 60,
) -> None:
    """
    记录“用户 -> App”维度的请求计数（分钟桶）。

    该指标以“入口请求”为准（/v1/chat/completions /v1/messages /v1/responses 都会走同一入口），
    避免将重试/多候选的上游调用次数误当作“使用次数”。
    """
    repo_record_user_app_request_metric(
        db,
        user_id=user_id,
        api_key_id=api_key_id,
        app_name=app_name,
        occurred_at=occurred_at,
        bucket_seconds=bucket_seconds,
    )


__all__ = ["record_user_app_request_metric"]
