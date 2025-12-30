"""
Celery 任务：用户自定义探针任务调度器。

按固定间隔扫描到期的 user_probe_tasks，并发起一次真实对话请求，将结果写入 user_probe_runs。
"""

from __future__ import annotations

import asyncio

from celery import shared_task

from app.celery_app import celery_app
from app.db import SessionLocal
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.services.user_probe_service import run_due_user_probe_tasks
from app.settings import settings


@shared_task(name="tasks.user_probe.run_due")
def run_due_user_probes() -> int:
    """
    扫描并执行到期的用户探针任务。

    Returns:
        实际执行的任务数量。
    """
    session = SessionLocal()
    try:
        async def _run() -> int:
            redis = get_redis_client()
            try:
                return await run_due_user_probe_tasks(
                    session=session,
                    redis=redis,
                    max_tasks=settings.user_probe_max_due_tasks_per_tick,
                )
            finally:
                await close_redis_client_for_current_loop()

        return asyncio.run(_run())
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "user-probe-run-due": {
            "task": "tasks.user_probe.run_due",
            "schedule": settings.user_probe_scheduler_interval_seconds,
        }
    }
)


__all__ = ["run_due_user_probes"]
