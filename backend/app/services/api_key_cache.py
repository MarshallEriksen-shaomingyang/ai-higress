from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.logging_config import logger
from app.models import APIKey
from app.redis_client import (
    close_redis_client_for_current_loop,
    get_redis_client,
    redis_delete,
    redis_get_json,
    redis_set_json,
)

CACHE_KEY_TEMPLATE = "auth:api-key:{key_hash}"
CACHE_TTL_SECONDS = 600


class CachedAPIKey(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    user_username: str
    user_is_active: bool
    user_is_superuser: bool
    name: str
    expires_at: datetime | None = None
    is_active: bool = True
    disabled_reason: str | None = None
    has_provider_restrictions: bool = False
    allowed_provider_ids: list[str] = Field(default_factory=list)


def build_cache_entry(api_key: APIKey) -> CachedAPIKey:
    user = api_key.user
    username = user.username if user is not None else ""
    is_active = user.is_active if user is not None else False
    is_superuser = user.is_superuser if user is not None else False
    return CachedAPIKey(
        id=str(api_key.id),
        user_id=str(api_key.user_id),
        user_username=username,
        user_is_active=is_active,
        user_is_superuser=is_superuser,
        name=api_key.name,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        disabled_reason=api_key.disabled_reason,
        has_provider_restrictions=api_key.has_provider_restrictions,
        allowed_provider_ids=list(api_key.allowed_provider_ids),
    )


async def get_cached_api_key(redis, key_hash: str) -> CachedAPIKey | None:
    key = CACHE_KEY_TEMPLATE.format(key_hash=key_hash)
    data = await redis_get_json(redis, key)
    if not data:
        return None
    try:
        return CachedAPIKey.model_validate(data)
    except ValidationError:
        await redis_delete(redis, key)
        return None


def _compute_ttl_seconds(entry: CachedAPIKey) -> int | None:
    ttl = CACHE_TTL_SECONDS
    if entry.expires_at is None:
        return ttl
    remaining = int(entry.expires_at.timestamp() - datetime.now(UTC).timestamp())
    if remaining <= 0:
        return 0
    return min(ttl, remaining)


async def cache_api_key(redis, key_hash: str, entry: CachedAPIKey) -> None:
    if not entry.is_active:
        await invalidate_cached_api_key(redis, key_hash)
        return
    ttl_seconds = _compute_ttl_seconds(entry)
    if ttl_seconds == 0:
        return
    key = CACHE_KEY_TEMPLATE.format(key_hash=key_hash)
    payload = entry.model_dump(mode="json")
    await redis_set_json(redis, key, payload, ttl_seconds=ttl_seconds)


async def invalidate_cached_api_key(redis, key_hash: str) -> None:
    key = CACHE_KEY_TEMPLATE.format(key_hash=key_hash)
    await redis_delete(redis, key)


def cache_api_key_sync(api_key: APIKey) -> None:
    """
    Best-effort helper to cache API key metadata from sync endpoints.
    """

    async def _cache() -> None:
        redis = get_redis_client()
        try:
            entry = build_cache_entry(api_key)
            await cache_api_key(redis, api_key.key_hash, entry)
        finally:
            await close_redis_client_for_current_loop()

    try:
        asyncio.run(_cache())
    except Exception:  # pragma: no cover - logging best-effort
        logger.exception("Failed to cache API key %s", api_key.id)


def invalidate_api_key_cache_sync(key_hash: str) -> None:
    """
    Best-effort helper to drop cached API key data from sync endpoints.
    """

    async def _invalidate() -> None:
        redis = get_redis_client()
        try:
            await invalidate_cached_api_key(redis, key_hash)
        finally:
            await close_redis_client_for_current_loop()

    try:
        asyncio.run(_invalidate())
    except Exception:  # pragma: no cover - logging best-effort
        logger.exception("Failed to invalidate API key cache for %s", key_hash)


__all__ = [
    "CACHE_KEY_TEMPLATE",
    "CachedAPIKey",
    "build_cache_entry",
    "cache_api_key",
    "cache_api_key_sync",
    "get_cached_api_key",
    "invalidate_api_key_cache_sync",
    "invalidate_cached_api_key",
]
