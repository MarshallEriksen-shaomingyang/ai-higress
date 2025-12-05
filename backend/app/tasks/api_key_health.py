"""
Celery 任务：定期巡检 API Key 过期与异常错误率。
"""

from __future__ import annotations

from celery import shared_task

from app.celery_app import celery_app
from app.db import SessionLocal
from app.logging_config import logger
from app.services.api_key_health import disable_error_prone_api_keys, disable_expired_api_keys
from app.settings import settings


@shared_task(name="tasks.api_key_health.disable_expired")
def disable_expired_api_keys_task() -> int:
    session = SessionLocal()
    try:
        disabled = disable_expired_api_keys(session)
        if disabled:
            logger.info("Disabled %s expired API keys", disabled)
        return disabled
    finally:
        session.close()


@shared_task(name="tasks.api_key_health.flag_error_prone")
def disable_error_prone_api_keys_task() -> int:
    session = SessionLocal()
    try:
        return disable_error_prone_api_keys(
            session,
            window_minutes=settings.api_key_error_window_minutes,
            error_rate_threshold=settings.api_key_error_rate_threshold,
            min_total_requests=settings.api_key_error_min_requests,
        )
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "api-key-expiry-scan": {
            "task": "tasks.api_key_health.disable_expired",
            "schedule": settings.api_key_health_check_interval_seconds,
        },
        "api-key-error-scan": {
            "task": "tasks.api_key_health.flag_error_prone",
            "schedule": settings.api_key_error_scan_interval_seconds,
        },
    }
)


__all__ = [
    "disable_error_prone_api_keys_task",
    "disable_expired_api_keys_task",
]
