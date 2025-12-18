from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import UserAppRequestMetricsHistory


def _current_bucket_start(now: dt.datetime, bucket_seconds: int) -> dt.datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    else:
        now = now.astimezone(dt.timezone.utc)

    epoch_seconds = int(now.timestamp())
    bucket_start = epoch_seconds - (epoch_seconds % bucket_seconds)
    return dt.datetime.fromtimestamp(bucket_start, tz=dt.timezone.utc)


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
    if not app_name:
        app_name = "unknown"

    try:
        at = occurred_at or dt.datetime.now(dt.timezone.utc)
        window_start = _current_bucket_start(at, bucket_seconds)

        dialect_name = getattr(db.get_bind(), "dialect", None)
        dialect_name = getattr(dialect_name, "name", None)

        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as upsert_insert

            conflict_kwargs = {"constraint": "uq_user_app_request_metrics_history_bucket"}
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert_insert

            conflict_kwargs = {
                "index_elements": [
                    UserAppRequestMetricsHistory.user_id,
                    UserAppRequestMetricsHistory.app_name,
                    UserAppRequestMetricsHistory.window_start,
                ]
            }

        insert_stmt = upsert_insert(UserAppRequestMetricsHistory).values(
            user_id=user_id,
            api_key_id=api_key_id,
            app_name=app_name,
            window_start=window_start,
            window_duration=bucket_seconds,
            total_requests=1,
        )
        stmt = insert_stmt.on_conflict_do_update(
            **conflict_kwargs,
            set_={
                "total_requests": UserAppRequestMetricsHistory.total_requests + 1,
                "updated_at": func.now(),
            },
        )
        db.execute(stmt)
        db.commit()
    except Exception:  # pragma: no cover - 指标不影响主流程
        try:
            db.rollback()
        except Exception:
            pass


__all__ = ["record_user_app_request_metric"]

