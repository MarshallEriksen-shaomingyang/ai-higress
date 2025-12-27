from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Provider
from app.provider.health import HealthStatus


def get_provider_by_provider_id(db: Session, *, provider_id: str) -> Provider | None:
    return db.query(Provider).filter(Provider.provider_id == provider_id).first()


def apply_health_status(db: Session, *, provider: Provider, status: HealthStatus) -> None:
    provider.status = status.status.value
    provider.last_check = datetime.fromtimestamp(status.timestamp, tz=UTC)
    provider.metadata_json = {
        "response_time_ms": status.response_time_ms,
        "error_message": status.error_message,
        "last_successful_check": status.last_successful_check,
    }
    db.add(provider)


__all__ = [
    "apply_health_status",
    "get_provider_by_provider_id",
]
