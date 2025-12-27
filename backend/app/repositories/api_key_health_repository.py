from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import APIKey, ProviderRoutingMetricsHistory


def disable_expired_api_keys(db: Session, *, now: datetime) -> list[APIKey]:
    stmt: Select[tuple[APIKey]] = select(APIKey).where(
        APIKey.is_active.is_(True),
        APIKey.expires_at.is_not(None),
        APIKey.expires_at <= now,
    )
    expired_keys = list(db.execute(stmt).scalars().all())
    if not expired_keys:
        return []

    for key in expired_keys:
        key.is_active = False
        key.disabled_reason = "expired"

    db.commit()
    return expired_keys


def disable_error_prone_api_keys(
    db: Session,
    *,
    window_start: datetime,
    error_rate_threshold: float,
    min_total_requests: int,
) -> list[APIKey]:
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
    target_ids = [row for row in db.execute(stmt).scalars().all()]
    if not target_ids:
        return []

    key_stmt: Select[tuple[APIKey]] = select(APIKey).where(
        APIKey.id.in_(target_ids),
        APIKey.is_active.is_(True),
    )
    affected = list(db.execute(key_stmt).scalars().all())
    if not affected:
        return []

    for key in affected:
        key.is_active = False
        key.disabled_reason = "high_error_rate"

    db.commit()
    return affected


__all__ = [
    "disable_error_prone_api_keys",
    "disable_expired_api_keys",
]

