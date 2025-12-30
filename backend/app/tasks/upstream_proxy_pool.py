"""
Celery 任务：上游代理池刷新与测活，并同步运行时可用集合到 Redis。

设计目标：
- DB 作为配置与健康状态的真相来源；
- Redis 存“当前可用代理集合（set）+ proxy_url 加密 token + url->id 反查映射 + cooldown keys”；
- request 侧仅从 Redis 取代理，失败时 best-effort 上报，让坏代理快速出池。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from celery import shared_task
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.celery_app import celery_app
from app.db import SessionLocal
from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.models import UpstreamProxyConfig, UpstreamProxyEndpoint, UpstreamProxySource
from app.repositories.upstream_proxy_repository import get_or_create_proxy_config, upsert_endpoints
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.services.upstream_proxy.redis import (
    clear_runtime_pool,
    in_cooldown,
    mark_available,
    put_endpoint_proxy_url,
    set_runtime_config,
)
from app.services.upstream_proxy.secrets import (
    build_endpoint_proxy_url,
    get_source_remote_headers,
    get_source_remote_url,
    utcnow,
)
from app.services.upstream_proxy.utils import parse_proxy_line, split_proxy_text
from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = Any  # type: ignore[misc,assignment]


async def _sync_config_to_redis(redis: Redis, cfg: UpstreamProxyConfig) -> None:
    await set_runtime_config(
        redis,
        enabled=bool(cfg.enabled),
        failure_cooldown_seconds=int(cfg.failure_cooldown_seconds),
    )


async def _refresh_remote_sources(session: Session) -> int:
    """
    Pull remote_text_list sources and upsert their endpoints.
    """
    stmt: Select[tuple[UpstreamProxySource]] = select(UpstreamProxySource).where(
        UpstreamProxySource.enabled.is_(True),
        UpstreamProxySource.source_type == "remote_text_list",
    )
    sources = list(session.execute(stmt).scalars().all())
    if not sources:
        return 0

    count = 0
    for source in sources:
        remote_url = None
        try:
            remote_url = get_source_remote_url(source)
        except Exception:
            remote_url = None

        if not remote_url:
            source.last_refresh_error = "remote_url 未配置"
            continue

        headers = get_source_remote_headers(source) or {}
        interval = source.refresh_interval_seconds or getattr(settings, "upstream_proxy_default_refresh_interval_seconds", 300)
        now = utcnow()
        if source.last_refresh_at is not None:
            elapsed = (now - source.last_refresh_at).total_seconds()
            if elapsed < interval:
                continue

        try:
            async with CurlCffiClient(timeout=10.0, trust_env=True) as client:
                resp = await client.get(remote_url, headers=headers)
                if resp.status_code >= 400:
                    raise Exception(f"HTTP {resp.status_code}: {resp.reason}")
                text = resp.text
            lines = split_proxy_text(text)
            parsed = []
            for line in lines:
                try:
                    parsed.append(parse_proxy_line(line, default_scheme=source.default_scheme))
                except Exception:
                    # Ignore malformed lines to keep the refresh resilient.
                    continue
            count += upsert_endpoints(session, source=source, proxies=parsed, mark_seen=True)
            source.last_refresh_at = now
            source.last_refresh_error = None
        except Exception as exc:
            # Do not log credentials; remote_url may embed tokens, so avoid printing it.
            source.last_refresh_at = now
            source.last_refresh_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "upstream_proxy: refresh remote source failed (source=%s id=%s): %s",
                source.name,
                source.id,
                exc,
            )
    session.commit()
    return count


async def _check_endpoint(
    *,
    redis: Redis,
    endpoint: UpstreamProxyEndpoint,
    check_url: str,
    method: str,
    timeout_ms: int,
) -> tuple[bool, float | None, str | None]:
    proxy_url = build_endpoint_proxy_url(endpoint)
    start = time.perf_counter()
    try:
        timeout_seconds = timeout_ms / 1000.0
        # 使用 proxies 参数来测试特定代理
        # curl-cffi 支持 proxies 字典或单个 proxy 字符串
        proxies = {"http": proxy_url, "https": proxy_url}
        async with CurlCffiClient(
            timeout=timeout_seconds,
            trust_env=False,  # 测试代理时不使用环境变量
            proxies=proxies,
        ) as client:
            if method.upper() == "GET":
                resp = await client.get(check_url)
            else:
                resp = await client.post(check_url)
        ok = resp.status_code < 400
        latency_ms = (time.perf_counter() - start) * 1000.0
        if ok:
            return True, latency_ms, None
        return False, latency_ms, f"bad_status:{resp.status_code}"
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, f"{type(exc).__name__}: {exc}"


async def _rebuild_runtime_available_set(
    *,
    redis: Redis,
    session: Session,
    enabled: bool,
) -> int:
    if not enabled:
        await clear_runtime_pool(redis)
        return 0

    await clear_runtime_pool(redis)

    stmt: Select[tuple[UpstreamProxyEndpoint]] = (
        select(UpstreamProxyEndpoint)
        .join(UpstreamProxySource, UpstreamProxyEndpoint.source_id == UpstreamProxySource.id)
        .where(
            UpstreamProxyEndpoint.enabled.is_(True),
            UpstreamProxySource.enabled.is_(True),
            UpstreamProxyEndpoint.last_ok.is_(True),
        )
    )
    endpoints = list(session.execute(stmt).scalars().all())
    for ep in endpoints:
        try:
            if await in_cooldown(redis, str(ep.id)):
                continue
            proxy_url = build_endpoint_proxy_url(ep)
            await put_endpoint_proxy_url(redis, endpoint_id=ep.id, proxy_url=proxy_url)
            await mark_available(redis, ep.id)
        except Exception:
            logger.exception("upstream_proxy: failed to sync endpoint to redis (id=%s)", ep.id)
    return len(endpoints)


async def _check_health_and_sync(session: Session) -> int:
    redis = get_redis_client()
    try:
        cfg = get_or_create_proxy_config(session)
        await _sync_config_to_redis(redis, cfg)

        # If disabled, just clear runtime pool and exit.
        if not cfg.enabled:
            await _rebuild_runtime_available_set(redis=redis, session=session, enabled=False)
            return 0

        now = utcnow()
        min_interval = int(cfg.healthcheck_interval_seconds)
        default_method = (cfg.healthcheck_method or "GET").upper()
        default_check_url = cfg.healthcheck_url
        default_timeout_ms = int(cfg.healthcheck_timeout_ms)

        stmt: Select[tuple[UpstreamProxyEndpoint]] = (
            select(UpstreamProxyEndpoint)
            .options(selectinload(UpstreamProxyEndpoint.source))
            .join(UpstreamProxySource, UpstreamProxyEndpoint.source_id == UpstreamProxySource.id)
            .where(
                UpstreamProxyEndpoint.enabled.is_(True),
                UpstreamProxySource.enabled.is_(True),
            )
        )
        endpoints = list(session.execute(stmt).scalars().all())
        to_check: list[UpstreamProxyEndpoint] = []
        for ep in endpoints:
            if ep.last_check_at is None:
                to_check.append(ep)
                continue
            elapsed = (now - ep.last_check_at).total_seconds()
            if elapsed >= min_interval:
                to_check.append(ep)

        # Limit concurrency to avoid creating too many TCP sockets at once.
        concurrency = getattr(settings, "upstream_proxy_healthcheck_concurrency", 20)
        sem = asyncio.Semaphore(int(concurrency))

        async def _run_one(ep: UpstreamProxyEndpoint) -> None:
            async with sem:
                if await in_cooldown(redis, str(ep.id)):
                    return
                # Source-level overrides (optional).
                source = getattr(ep, "source", None)
                check_url = getattr(source, "healthcheck_url", None) or default_check_url
                method = (getattr(source, "healthcheck_method", None) or default_method).upper()
                timeout_ms = int(getattr(source, "healthcheck_timeout_ms", None) or default_timeout_ms)
                ok, latency_ms, err = await _check_endpoint(
                    redis=redis,
                    endpoint=ep,
                    check_url=check_url,
                    method=method,
                    timeout_ms=timeout_ms,
                )
                ep.last_check_at = utcnow()
                ep.last_ok = ok
                ep.last_latency_ms = latency_ms
                if ok:
                    ep.consecutive_failures = 0
                    ep.last_error = None
                else:
                    ep.consecutive_failures = int(ep.consecutive_failures or 0) + 1
                    ep.last_error = err

        await asyncio.gather(*[_run_one(ep) for ep in to_check])
        session.commit()

        await _rebuild_runtime_available_set(redis=redis, session=session, enabled=True)
        return len(to_check)
    finally:
        await close_redis_client_for_current_loop()


@shared_task(name="tasks.upstream_proxy.refresh_sources")
def refresh_upstream_proxy_sources() -> int:
    session = SessionLocal()
    try:
        async def _run() -> int:
            cfg = get_or_create_proxy_config(session)
            redis = get_redis_client()
            try:
                await _sync_config_to_redis(redis, cfg)
                return await _refresh_remote_sources(session)
            finally:
                await close_redis_client_for_current_loop()

        return asyncio.run(_run())
    finally:
        session.close()


@shared_task(name="tasks.upstream_proxy.check_health")
def check_upstream_proxies_health() -> int:
    session = SessionLocal()
    try:
        return asyncio.run(_check_health_and_sync(session))
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        "upstream-proxy-refresh-sources": {
            "task": "tasks.upstream_proxy.refresh_sources",
            "schedule": getattr(settings, "upstream_proxy_refresh_scheduler_interval_seconds", 60),
        },
        "upstream-proxy-health-check": {
            "task": "tasks.upstream_proxy.check_health",
            "schedule": getattr(settings, "upstream_proxy_healthcheck_scheduler_interval_seconds", 60),
        },
    }
)


__all__ = ["check_upstream_proxies_health", "refresh_upstream_proxy_sources"]
