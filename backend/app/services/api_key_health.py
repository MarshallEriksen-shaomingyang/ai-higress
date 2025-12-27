from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import logger
from app.repositories.api_key_health_repository import (
    disable_error_prone_api_keys as repo_disable_error_prone_api_keys,
    disable_expired_api_keys as repo_disable_expired_api_keys,
)
from app.schemas.notification import NotificationCreateRequest
from app.services.api_key_cache import invalidate_api_key_cache_sync
from app.services.notification_service import create_notification


def disable_expired_api_keys(session: Session, *, now: datetime | None = None) -> int:
    """
    将已过期但仍处于激活状态的 API Key 标记为不可用。
    """

    current = now or datetime.now(UTC)
    expired_keys = repo_disable_expired_api_keys(session, now=current)
    if not expired_keys:
        return 0

    for key in expired_keys:
        invalidate_api_key_cache_sync(key.key_hash)
        try:
            create_notification(
                session,
                NotificationCreateRequest(
                    title="API Key 已过期并被禁用",
                    content=f"API Key {key.name} 已于 {current.isoformat()} 过期并被自动禁用。",
                    level="warning",
                    target_type="users",
                    target_user_ids=[UUID(str(key.user_id))],
                ),
                creator_id=None,
            )
        except Exception:  # pragma: no cover - 通知失败不影响主流程
            logger.exception("Failed to send notification for expired API key %s", key.id)
    return len(expired_keys)


def disable_error_prone_api_keys(
    session: Session,
    *,
    window_minutes: int,
    error_rate_threshold: float,
    min_total_requests: int,
    now: datetime | None = None,
) -> int:
    """
    基于路由指标将高错误率的 API Key 置为不可用。
    """

    current = now or datetime.now(UTC)
    window_start = current - timedelta(minutes=window_minutes)
    affected = repo_disable_error_prone_api_keys(
        session,
        window_start=window_start,
        error_rate_threshold=error_rate_threshold,
        min_total_requests=min_total_requests,
    )
    if not affected:
        return 0
    for key in affected:
        invalidate_api_key_cache_sync(key.key_hash)
        try:
            create_notification(
                session,
                NotificationCreateRequest(
                    title="API Key 因高错误率被禁用",
                    content=(
                        f"API Key {key.name} 在最近 {window_minutes} 分钟内错误率过高，"
                        "已被自动禁用，请检查上游或重新启用。"
                    ),
                    level="warning",
                    target_type="users",
                    target_user_ids=[UUID(str(key.user_id))],
                ),
                creator_id=None,
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to send notification for high-error API key %s", key.id
            )

    logger.info(
        "Disabled %s API keys due to high error rate (>=%.2f) in last %s minutes",
        len(affected),
        error_rate_threshold,
        window_minutes,
    )
    return len(affected)


__all__ = ["disable_error_prone_api_keys", "disable_expired_api_keys"]
