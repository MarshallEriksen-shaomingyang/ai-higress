from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import APIKey, ProviderRoutingMetricsHistory
from app.services.api_key_cache import invalidate_api_key_cache_sync


def disable_expired_api_keys(session: Session, *, now: datetime | None = None) -> int:
    """
    将已过期但仍处于激活状态的 API Key 标记为不可用。
    """

    current = now or datetime.now(UTC)
    stmt: Select[tuple[APIKey]] = select(APIKey).where(
        APIKey.is_active.is_(True),
        APIKey.expires_at.is_not(None),
        APIKey.expires_at <= current,
    )
    expired_keys = list(session.execute(stmt).scalars().all())
    if not expired_keys:
        return 0

    for key in expired_keys:
        key.is_active = False
        key.disabled_reason = "expired"

    session.commit()

    for key in expired_keys:
        invalidate_api_key_cache_sync(key.key_hash)
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

    stmt: Select[tuple[str]] = (
        select(ProviderRoutingMetricsHistory.api_key_id)
        .where(
            ProviderRoutingMetricsHistory.api_key_id.is_not(None),
            ProviderRoutingMetricsHistory.window_start >= window_start,
            ProviderRoutingMetricsHistory.total_requests_1m >= min_total_requests,
            ProviderRoutingMetricsHistory.error_rate >= error_rate_threshold,
        )
        .distinct()
    )
    target_ids = [row for row in session.execute(stmt).scalars().all()]
    if not target_ids:
        return 0

    key_stmt: Select[tuple[APIKey]] = select(APIKey).where(
        APIKey.id.in_(target_ids),
        APIKey.is_active.is_(True),
    )
    affected = list(session.execute(key_stmt).scalars().all())
    if not affected:
        return 0

    for key in affected:
        key.is_active = False
        key.disabled_reason = "high_error_rate"

    session.commit()
    for key in affected:
        invalidate_api_key_cache_sync(key.key_hash)

    logger.info(
        "Disabled %s API keys due to high error rate (>=%.2f) in last %s minutes",
        len(affected),
        error_rate_threshold,
        window_minutes,
    )
    return len(affected)


__all__ = ["disable_error_prone_api_keys", "disable_expired_api_keys"]
