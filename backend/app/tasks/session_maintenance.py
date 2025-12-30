"""
Celery 任务：定期巡检并清理 Redis 中的用户会话索引。

- 扫描 auth:user:{user_id}:sessions 键；
- 对每个用户会话列表调用 TokenRedisService.cleanup_user_sessions()，
  清理无效或损坏的会话记录；
- 该任务只负责索引层的「垃圾回收」，真正的 token 失效仍然依赖
  JWT 过期时间、黑名单以及业务侧的 revoke_* 调用。
"""

from __future__ import annotations

import asyncio

from celery import shared_task

from app.celery_app import celery_app
from app.logging_config import logger
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.services.token_redis_service import USER_SESSIONS_KEY, TokenRedisService
from app.settings import settings


async def _cleanup_all_sessions() -> int:
    """
    扫描所有用户会话索引并执行清理。

    Returns:
        实际移除的会话总数
    """
    redis = get_redis_client()
    try:
        service = TokenRedisService(redis)

        # 使用 Redis 的 scan_iter 逐步扫描，以避免阻塞
        pattern = USER_SESSIONS_KEY.format(user_id="*")
        total_removed = 0

        async for key in redis.scan_iter(match=pattern):
            # 预期 key 形如 auth:user:{user_id}:sessions
            try:
                # 不强依赖精确的分段数量，最低保证 user_id 在倒数第二段
                parts = str(key).split(":")
                if len(parts) < 4:
                    continue
                user_id = parts[2]
            except Exception:
                continue

            removed = await service.cleanup_user_sessions(user_id)
            if removed:
                total_removed += removed
                logger.info(
                    "Cleaned %s invalid sessions for user %s",
                    removed,
                    user_id,
                )

        return total_removed
    finally:
        await close_redis_client_for_current_loop()


@shared_task(name="tasks.sessions.cleanup_all")
def cleanup_all_user_sessions_task() -> int:
    """
    Celery 入口：定期清理所有用户会话索引中的无效/损坏记录。
    """

    def _run() -> int:
        return asyncio.run(_cleanup_all_sessions())

    removed = _run()
    if removed:
        logger.info("User session cleanup finished, removed %s stale sessions", removed)
    else:
        logger.debug("User session cleanup finished, no stale sessions found")
    return removed


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "user-session-cleanup": {
            "task": "tasks.sessions.cleanup_all",
            "schedule": settings.user_session_cleanup_interval_seconds,
        }
    }
)


__all__ = ["cleanup_all_user_sessions_task"]
