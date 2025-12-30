from __future__ import annotations

"""
Celery 任务定义入口。

当前只提供少量基础任务：
- debug_ping: 简单的 ping/pong 测试任务，用于验证 Celery worker 是否正常工作；
- sync_logical_models_task: 异步刷新 Redis 中的逻辑模型缓存，
  后续可以扩展为定时任务或在 Provider 变更后触发。
"""

import asyncio
from collections.abc import Sequence

from celery import shared_task

from app.logging_config import logger
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.services.logical_model_sync import sync_logical_models


@shared_task(name="tasks.debug_ping")
def debug_ping() -> str:
    """
    简单的 Celery 测试任务。

    用法示例（在容器 / 本地虚拟环境中）:
        celery -A app.celery_app.celery_app call tasks.debug_ping
    """

    logger.info("Celery debug_ping task executed")
    return "pong"


@shared_task(name="tasks.sync_logical_models")
def sync_logical_models_task(provider_ids: Sequence[str] | None = None) -> int:
    """
    通过 Celery 异步刷新 Redis 中的逻辑模型缓存。

    Args:
        provider_ids: 可选，只同步指定 provider_id 列表；为 None 时执行全量刷新。

    Returns:
        实际写入（或更新）的逻辑模型数量。
    """

    async def _run() -> int:
        redis = get_redis_client()
        try:
            logical_models = await sync_logical_models(redis, provider_ids=provider_ids)
            logger.info(
                "Celery sync_logical_models_task finished: %d logical models synced (providers=%s)",
                len(logical_models),
                list(provider_ids) if provider_ids is not None else "ALL",
            )
            return len(logical_models)
        finally:
            await close_redis_client_for_current_loop()

    # 在 Celery 同步任务中执行异步逻辑。
    return asyncio.run(_run())


__all__ = ["debug_ping", "sync_logical_models_task"]
