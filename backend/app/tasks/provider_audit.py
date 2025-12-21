from __future__ import annotations

"""
Celery 任务：自动探针与巡检。
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

from app.celery_app import celery_app
from app.db import SessionLocal
from app.logging_config import logger
from app.models import Provider
from app.services.provider_audit_service import (
    ProviderAuditError,
    ProviderNotFoundError,
    trigger_provider_test,
    update_operation_status,
)
from app.settings import settings


def _get_public_providers(session, audit_statuses: Sequence[str] | None = None):
    stmt = select(Provider).where(Provider.visibility == "public")
    if audit_statuses:
        stmt = stmt.where(Provider.audit_status.in_(list(audit_statuses)))
    return list(session.execute(stmt).scalars().all())


def _auto_probe_provider(session, provider: Provider, mode: str, remark: str | None = None):
    # 跳过未开启探针的 Provider
    if provider.probe_enabled is False:
        logger.info("Skip probe for %s (disabled)", provider.provider_id)
        return
    # 跳过未到频率的巡检
    interval_seconds = provider.probe_interval_seconds
    if interval_seconds is None:
        interval_seconds = (
            settings.provider_audit_auto_probe_interval_seconds
            if mode == "auto"
            else settings.provider_audit_cron_interval_seconds
        )
    if provider.last_check and interval_seconds:
        delta = (datetime.now(UTC) - provider.last_check).total_seconds()
        if delta < interval_seconds:
            logger.info(
                "Skip probe for %s: %.1fs < interval %ss",
                provider.provider_id,
                delta,
                interval_seconds,
            )
            return

    try:
        record = trigger_provider_test(
            session,
            provider.provider_id,
            operator_id=None,
            mode=mode,  # auto | cron
            remark=remark,
        )
        # 自动降级：探针失败则暂停运营
        if not record.success:
            update_operation_status(
                session,
                provider.provider_id,
                operator_id=None,
                new_status="paused",
                remark="auto probe failed",
            )
    except ProviderNotFoundError:
        logger.warning("Auto probe skip: provider %s not found", provider.provider_id)
    except ProviderAuditError as exc:
        logger.warning("Auto probe failed for %s: %s", provider.provider_id, exc)
    except Exception:  # pragma: no cover - 防御性记录
        logger.exception("Auto probe unexpected error for %s", provider.provider_id)


@shared_task(name="tasks.provider_audit.auto_probe_pending")
def auto_probe_pending_providers() -> int:
    """对待审核 Provider 进行自动探针测试。"""

    session = SessionLocal()
    try:
        providers = _get_public_providers(session, audit_statuses=("pending", "testing"))
        logger.info("Auto probe pending providers: %d found", len(providers))
        for provider in providers:
            _auto_probe_provider(session, provider, mode="auto", remark="pending auto probe")
        return len(providers)
    finally:
        session.close()


@shared_task(name="tasks.provider_audit.cron_inspect_live_providers")
def cron_inspect_live_providers() -> int:
    """
    巡检已上线 Provider（审核通过）并自动降级异常。
    """

    session = SessionLocal()
    try:
        providers = _get_public_providers(session, audit_statuses=("approved", "approved_limited"))
        logger.info("Cron inspect providers: %d approved providers", len(providers))
        for provider in providers:
            _auto_probe_provider(session, provider, mode="cron", remark="cron inspect")
        return len(providers)
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "provider-auto-probe-pending": {
            "task": "tasks.provider_audit.auto_probe_pending",
            "schedule": settings.provider_audit_auto_probe_interval_seconds,
        },
        "provider-cron-inspect": {
            "task": "tasks.provider_audit.cron_inspect_live_providers",
            "schedule": settings.provider_audit_cron_interval_seconds,
        },
    }
)


__all__ = [
    "auto_probe_pending_providers",
    "cron_inspect_live_providers",
]
