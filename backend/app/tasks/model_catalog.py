"""
定时刷新 models.dev 公共模型目录。
"""

from __future__ import annotations

import asyncio

from celery import shared_task

from app.celery_app import celery_app
from app.logging_config import logger
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.services.model_catalog_service import refresh_models_dev_catalog
from app.settings import settings


@shared_task(name="tasks.model_catalog.refresh_models_dev")
def refresh_models_dev_catalog_task() -> dict:
    """
    Celery 任务：拉取 models.dev 并写入 Redis。
    """

    async def _run():
        redis = get_redis_client()
        try:
            return await refresh_models_dev_catalog(redis, force=False)
        finally:
            await close_redis_client_for_current_loop()

    result = asyncio.run(_run())
    logger.info(
        "模型目录刷新任务完成：refreshed=%s providers=%s models=%s",
        result.get("refreshed"),
        result.get("provider_count"),
        result.get("model_count"),
    )
    return result


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "refresh-models-dev-catalog": {
            "task": "tasks.model_catalog.refresh_models_dev",
            # 默认每 3 天刷新一次，可通过环境变量覆盖（单位：秒）
            "schedule": getattr(
                settings, "models_dev_refresh_interval_seconds", 60 * 60 * 24 * 3
            ),
        },
    }
)


__all__ = ["refresh_models_dev_catalog_task"]
