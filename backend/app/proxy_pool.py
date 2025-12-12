from __future__ import annotations

import asyncio
import random
import re
from urllib.parse import urlparse

from app.logging_config import logger
from app.settings import settings

_VALID_PROXY_SCHEMES = {"http", "https", "socks5", "socks5h"}


def _parse_proxy_pool(raw: str) -> list[str]:
    """
    Parse UPSTREAM_PROXY_POOL from env.

    Accept comma/newline/semicolon separated URLs. Invalid entries are ignored.
    """
    if not raw:
        return []
    items = [s.strip() for s in re.split(r"[,\n;]+", raw) if s.strip()]
    proxies: list[str] = []
    for item in items:
        try:
            parsed = urlparse(item)
        except Exception:  # pragma: no cover - 极端输入
            parsed = None
        if not parsed or not parsed.scheme or not parsed.netloc:
            logger.warning("upstream_proxy_pool: 忽略无效代理 URL: %r", item)
            continue
        if parsed.scheme.lower() not in _VALID_PROXY_SCHEMES:
            logger.warning(
                "upstream_proxy_pool: 忽略不支持的代理协议 %r (url=%s)",
                parsed.scheme,
                item,
            )
            continue
        proxies.append(item)
    return proxies


class ProxyPool:
    """
    Lightweight proxy pool for upstream requests.

    Strategy:
    - random: every pick is random choice.
    - round_robin: sequential picks across the pool.
    """

    def __init__(self, proxies: list[str], strategy: str = "random") -> None:
        self._proxies = proxies
        self._strategy = (strategy or "random").lower()
        self._idx = 0
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self._proxies)

    async def pick(self, *, exclude: set[str] | None = None) -> str | None:
        if not self._proxies:
            return None
        exclude = exclude or set()
        if self._strategy == "round_robin":
            async with self._lock:
                if not exclude:
                    proxy = self._proxies[self._idx % len(self._proxies)]
                    self._idx += 1
                    return proxy
                start = self._idx
                n = len(self._proxies)
                for i in range(n):
                    proxy = self._proxies[(start + i) % n]
                    if proxy not in exclude:
                        self._idx = start + i + 1
                        return proxy
                # All excluded: just return next in order.
                proxy = self._proxies[start % n]
                self._idx = start + 1
                return proxy
        # Default to random to spread requests across IPs.
        eligible = [p for p in self._proxies if p not in exclude]
        if not eligible:
            eligible = self._proxies
        return random.choice(eligible)


_proxy_pool: ProxyPool | None = None
_proxy_pool_lock = asyncio.Lock()


async def get_upstream_proxy_pool() -> ProxyPool | None:
    """
    Get a singleton ProxyPool built from settings.
    """
    global _proxy_pool
    if _proxy_pool is not None:
        return _proxy_pool if _proxy_pool.enabled else None

    async with _proxy_pool_lock:
        if _proxy_pool is None:
            proxies = _parse_proxy_pool(settings.upstream_proxy_pool)
            _proxy_pool = ProxyPool(proxies, settings.upstream_proxy_strategy)
            if proxies:
                logger.info(
                    "upstream_proxy_pool: 已启用代理池，数量=%d，策略=%s",
                    len(proxies),
                    settings.upstream_proxy_strategy,
                )
            else:
                logger.info("upstream_proxy_pool: 未配置代理池，保持直连")
    return _proxy_pool if _proxy_pool.enabled else None


async def pick_upstream_proxy(*, exclude: set[str] | None = None) -> str | None:
    pool = await get_upstream_proxy_pool()
    if not pool:
        return None
    return await pool.pick(exclude=exclude)


__all__ = ["ProxyPool", "get_upstream_proxy_pool", "pick_upstream_proxy"]
