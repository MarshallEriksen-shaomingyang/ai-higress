"""
Celery 任务：定时巡检 Provider 健康状态并写入 Redis/数据库。

- 采用旁路缓存：读取时优先 Redis，miss 时回退数据库；
- 写入时同时更新数据库与 Redis，Redis 设置 TTL 以保证状态不陈旧。
"""

from __future__ import annotations

import asyncio
from typing import Any, Sequence, TYPE_CHECKING

import httpx
from celery import shared_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db import SessionLocal
from app.provider.config import load_providers_with_configs
from app.provider.health import check_provider_health
from app.redis_client import get_redis_client
from app.services.provider_health_service import persist_provider_health
from app.settings import settings

if TYPE_CHECKING:  # pragma: no cover - typing hint only
    from redis.asyncio import Redis
else:  # pragma: no cover - fallback type when redis isn't installed
    Redis = Any


async def _run_checks(
    redis: Redis,
    session: Session,
    *,
    provider_ids: Sequence[str] | None = None,
    cache_ttl_seconds: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> int:
    owns_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=settings.upstream_timeout)
        owns_client = True

    try:
        pairs = load_providers_with_configs(session=session)
        count = 0
        for provider, cfg in pairs:
            if provider_ids is not None and provider.provider_id not in provider_ids:
                continue
            status = await check_provider_health(client, cfg, redis)
            await persist_provider_health(
                redis,
                session,
                provider,
                status,
                cache_ttl_seconds=cache_ttl_seconds,
            )
            count += 1
        session.commit()
        return count
    finally:
        if owns_client:
            await client.aclose()


@shared_task(name="tasks.provider_health.check_all")
def check_all_providers_health() -> int:
    """巡检所有可用 Provider 的健康状态。"""

    redis = get_redis_client()
    session = SessionLocal()

    try:
        return asyncio.run(
            _run_checks(
                redis,
                session,
                cache_ttl_seconds=settings.provider_health_cache_ttl_seconds,
            )
        )
    finally:
        session.close()


@shared_task(name="tasks.provider_health.check_subset")
def check_selected_providers_health(provider_ids: Sequence[str]) -> int:
    """巡检指定 provider_id 列表的健康状态。"""

    redis = get_redis_client()
    session = SessionLocal()

    try:
        return asyncio.run(
            _run_checks(
                redis,
                session,
                provider_ids=provider_ids,
                cache_ttl_seconds=settings.provider_health_cache_ttl_seconds,
            )
        )
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "provider-health-check": {
            "task": "tasks.provider_health.check_all",
            "schedule": settings.provider_health_check_interval_seconds,
        }
    }
)


__all__ = ["check_all_providers_health", "check_selected_providers_health"]
