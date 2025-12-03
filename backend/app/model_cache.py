import json
from typing import Any

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from .settings import settings

# Aggregated /models cache key (no longer tied to legacy A4F upstream).
MODELS_CACHE_KEY = "gateway:models:all"


async def get_models_from_cache(redis: Redis) -> dict[str, Any] | None:
    """
    Return cached models payload if present, otherwise None.
    """
    raw = await redis.get(MODELS_CACHE_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Corrupted cache; treat as cache miss.
        return None


async def set_models_cache(redis: Redis, data: dict[str, Any]) -> None:
    """
    Store models payload into cache with TTL.
    """
    ttl = settings.models_cache_ttl
    await redis.set(MODELS_CACHE_KEY, json.dumps(data), ex=ttl)
