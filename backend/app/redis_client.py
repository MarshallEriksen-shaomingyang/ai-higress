"""
Redis helper utilities for the routing layer.

Existing code uses `app.deps.get_redis` as a FastAPI dependency.
This module provides a central place to construct the Redis client and
some small helpers for JSON-style key access so that new routing /
provider components do not duplicate this logic.
"""

from __future__ import annotations

import json
from typing import Any

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - allows running without redis installed
    Redis = object  # type: ignore[misc,assignment]

from .settings import settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """
    Return a lazily-created global Redis client.

    This is intentionally sync so it can be reused both from FastAPI
    dependencies and background tasks. The underlying driver is fully
    async and should be awaited by callers.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def redis_get_json(redis: Redis, key: str) -> Any | None:
    """
    Convenience wrapper that loads a JSON value from Redis.
    Returns None on missing key or malformed payload.
    """
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def redis_set_json(
    redis: Redis, key: str, value: Any, *, ttl_seconds: int | None = None
) -> None:
    """
    Store a JSON-serialisable value under the given key with optional TTL.
    """
    data = json.dumps(value, ensure_ascii=False)
    if ttl_seconds is not None:
        await redis.set(key, data, ex=ttl_seconds)
    else:
        await redis.set(key, data)


async def redis_delete(redis: Redis, key: str) -> None:
    """
    Delete a key if it exists.
    """
    await redis.delete(key)


__all__ = ["get_redis_client", "redis_delete", "redis_get_json", "redis_set_json"]
