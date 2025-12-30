"""
Redis helper utilities for the routing layer.

Existing code uses `app.deps.get_redis` as a FastAPI dependency.
This module provides a central place to construct the Redis client and
some small helpers for JSON-style key access so that new routing /
provider components do not duplicate this logic.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any
from weakref import WeakKeyDictionary

from fastapi.encoders import jsonable_encoder

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - allows running without redis installed
    Redis = object  # type: ignore[misc,assignment]

from .settings import settings

_redis_clients_by_loop: WeakKeyDictionary[asyncio.AbstractEventLoop, Redis] = (
    WeakKeyDictionary()
)


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError as exc:  # pragma: no cover - easier debugging for sync misuse
        raise RuntimeError(
            "get_redis_client() 必须在运行中的事件循环内调用，请在 async 环境或 "
            "asyncio.run(...) 内部获取 Redis 客户端"
        ) from exc


def _create_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis_client() -> Redis:
    """
    Return a Redis client bound to the current event loop.
    """

    loop = _ensure_event_loop()
    client = _redis_clients_by_loop.get(loop)
    if client is None:
        client = _create_client()
        _redis_clients_by_loop[loop] = client
    return client


async def _maybe_await(result: Any) -> None:
    if inspect.isawaitable(result):
        await result


async def close_redis_client(client: Any) -> None:
    """
    Best-effort close for redis-py asyncio client instances.

    This is primarily used by short-lived event loops (e.g. Celery tasks using
    asyncio.run), to avoid leaking TCP sockets / file descriptors.
    """

    close_fn = getattr(client, "aclose", None)
    if callable(close_fn):
        await _maybe_await(close_fn())
    else:
        close_fn = getattr(client, "close", None)
        if callable(close_fn):
            await _maybe_await(close_fn())

    # As a final safety net, try disconnecting the underlying connection pool.
    pool = getattr(client, "connection_pool", None)
    disconnect_fn = getattr(pool, "disconnect", None)
    if callable(disconnect_fn):
        try:
            await _maybe_await(disconnect_fn(inuse_connections=True))
        except TypeError:
            await _maybe_await(disconnect_fn())


async def close_redis_client_for_current_loop() -> None:
    """
    Close and forget the cached Redis client for the current running loop.
    """

    loop = _ensure_event_loop()
    client = _redis_clients_by_loop.pop(loop, None)
    if client is None:
        return
    await close_redis_client(client)


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
    serialisable_value = jsonable_encoder(value)
    data = json.dumps(serialisable_value, ensure_ascii=False)
    if ttl_seconds is not None:
        await redis.set(key, data, ex=ttl_seconds)
    else:
        await redis.set(key, data)


async def redis_delete(redis: Redis, key: str) -> None:
    """
    Delete a key if it exists.
    """
    await redis.delete(key)


__all__ = [
    "close_redis_client",
    "close_redis_client_for_current_loop",
    "get_redis_client",
    "redis_delete",
    "redis_get_json",
    "redis_set_json",
]
