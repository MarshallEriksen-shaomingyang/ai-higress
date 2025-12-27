from __future__ import annotations

import time

from app.logging_config import logger
from app.services.upstream_proxy.redis import (
    get_endpoint_proxy_url,
    get_runtime_config,
    pick_available_proxy_id,
    report_failure_by_proxy_url,
)

_managed_runtime_enabled: bool | None = None
_managed_failure_cooldown_seconds: int = 120
_managed_cfg_cache_until: float = 0.0
_managed_cfg_cache_ttl_seconds: float = 5.0


async def pick_upstream_proxy(*, exclude: set[str] | None = None) -> str | None:
    """
    Pick a proxy URL for upstream calls.

    Notes:
    - 仅支持“管理式代理池”（DB 配置 + Celery 测活 + Redis 可用集合）。
    - 不再从环境变量读取代理。
    """
    exclude = exclude or set()

    # Managed pool (Redis). Any runtime error results in "no proxy" (direct).
    try:
        from app.redis_client import get_redis_client

        redis = get_redis_client()
        now = time.monotonic()

        global _managed_cfg_cache_until, _managed_failure_cooldown_seconds, _managed_runtime_enabled

        # Refresh runtime flags periodically (or after cache expiry).
        if now >= _managed_cfg_cache_until:
            try:
                cfg = await get_runtime_config(redis)
                enabled = (cfg.get("enabled") or "0") == "1"
                _managed_runtime_enabled = enabled
                cooldown_raw = cfg.get("failure_cooldown_seconds")
                if cooldown_raw and cooldown_raw.isdigit():
                    _managed_failure_cooldown_seconds = int(cooldown_raw)
                _managed_cfg_cache_until = now + _managed_cfg_cache_ttl_seconds
            except Exception as exc:
                # If Redis is down, avoid spamming connection attempts for a short period.
                _managed_runtime_enabled = False
                _managed_cfg_cache_until = now + _managed_cfg_cache_ttl_seconds
                logger.debug("upstream_proxy: runtime config read failed: %s", exc)

        if not _managed_runtime_enabled:
            return None

        exclude_ids: set[str] = set()
        for _ in range(8):
            endpoint_id = await pick_available_proxy_id(redis, exclude_ids=exclude_ids)
            if not endpoint_id:
                return None
            proxy_url = await get_endpoint_proxy_url(redis, endpoint_id)
            if not proxy_url:
                exclude_ids.add(endpoint_id)
                continue
            if proxy_url in exclude:
                exclude_ids.add(endpoint_id)
                continue
            return proxy_url
        return None
    except Exception as exc:
        logger.debug("upstream_proxy: managed pool pick failed, use direct: %s", exc)
        return None


async def report_upstream_proxy_failure(proxy_url: str) -> None:
    """
    Request-side proxy failure feedback (best-effort).

    This is intentionally non-blocking/forgiving: any internal error is swallowed
    so that upstream requests do not fail because Redis is unavailable.
    """
    # Most requests won't use managed proxies; avoid hitting Redis on failures unless enabled.
    if _managed_runtime_enabled is not True:
        return
    cooldown_seconds = _managed_failure_cooldown_seconds

    await report_failure_by_proxy_url(
        proxy_url=proxy_url,
        cooldown_seconds=cooldown_seconds,
    )


__all__ = [
    "pick_upstream_proxy",
    "report_upstream_proxy_failure",
]
