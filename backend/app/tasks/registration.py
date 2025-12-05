from __future__ import annotations

from uuid import UUID

from app.celery_app import celery_app
from app.db import SessionLocal
from app.logging_config import logger
from app.services.registration_window_service import (
    activate_window_by_id,
    close_window_by_id,
)


@celery_app.task(name="registration.activate_window")
def activate_registration_window(window_id: str) -> None:
    session = SessionLocal()
    try:
        activate_window_by_id(session, UUID(window_id))
    except Exception:  # pragma: no cover - defensive logging for worker failures
        logger.exception("Failed to activate registration window %s", window_id)
    finally:
        session.close()


@celery_app.task(name="registration.close_window")
def close_registration_window(window_id: str) -> None:
    session = SessionLocal()
    try:
        close_window_by_id(session, UUID(window_id))
    except Exception:  # pragma: no cover - defensive logging for worker failures
        logger.exception("Failed to close registration window %s", window_id)
    finally:
        session.close()


__all__ = ["activate_registration_window", "close_registration_window"]
