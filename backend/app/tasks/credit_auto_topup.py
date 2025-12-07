"""
Celery 任务：根据配置为用户自动充值积分。

- 按固定间隔（默认每日一次）扫描启用的自动充值规则；
- 当某个用户的积分余额低于阈值时，自动将余额补足到指定数值。
"""

from __future__ import annotations

from celery import shared_task

from app.celery_app import celery_app
from app.db import SessionLocal
from app.logging_config import logger
from app.services.credit_service import run_daily_auto_topups
from app.settings import settings


@shared_task(name="tasks.credits.run_daily_auto_topups")
def run_daily_auto_topups_task() -> int:
    """
    执行一次自动积分充值扫描。

    返回本次实际执行充值的账户数量。
    """
    session = SessionLocal()
    try:
        count = run_daily_auto_topups(session)
        if count:
            logger.info("Auto topped up credits for %s accounts", count)
        return count
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "credits-auto-topup-daily": {
            "task": "tasks.credits.run_daily_auto_topups",
            "schedule": settings.credits_auto_topup_interval_seconds,
        }
    }
)


__all__ = ["run_daily_auto_topups_task"]

