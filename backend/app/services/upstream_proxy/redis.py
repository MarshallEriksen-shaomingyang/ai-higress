from __future__ import annotations

from typing import Any
from uuid import UUID

from app.logging_config import logger
from app.services.encryption import decrypt_secret, encrypt_secret

from .utils import compute_url_fingerprint

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = Any  # type: ignore[misc,assignment]


def _available_set_key() -> str:
    return "upstream_proxy:available"


def _endpoint_url_key(endpoint_id: UUID | str) -> str:
    return f"upstream_proxy:endpoint:{endpoint_id}:url"


def _cooldown_key(endpoint_id: UUID | str) -> str:
    return f"upstream_proxy:cooldown:{endpoint_id}"


def _url_to_id_key(fingerprint: str) -> str:
    return f"upstream_proxy:url_to_id:{fingerprint}"


def _cfg_key(name: str) -> str:
    return f"upstream_proxy:config:{name}"


async def get_runtime_config(redis: Redis) -> dict[str, str | None]:
    # Small batch read; keep tolerant.
    enabled = await redis.get(_cfg_key("enabled"))
    cooldown = await redis.get(_cfg_key("failure_cooldown_seconds"))
    return {
        "enabled": enabled,
        "failure_cooldown_seconds": cooldown,
    }


async def set_runtime_config(
    redis: Redis,
    *,
    enabled: bool,
    failure_cooldown_seconds: int,
) -> None:
    await redis.set(_cfg_key("enabled"), "1" if enabled else "0")
    await redis.set(_cfg_key("failure_cooldown_seconds"), str(int(failure_cooldown_seconds)))


async def clear_runtime_pool(redis: Redis) -> None:
    # Remove availability set; per-endpoint url keys are cleaned lazily.
    await redis.delete(_available_set_key())


async def put_endpoint_proxy_url(
    redis: Redis,
    *,
    endpoint_id: UUID,
    proxy_url: str,
) -> None:
    token = encrypt_secret(proxy_url).decode("ascii")
    await redis.set(_endpoint_url_key(endpoint_id), token)
    fp = compute_url_fingerprint(proxy_url)
    await redis.set(_url_to_id_key(fp), str(endpoint_id))


async def get_endpoint_proxy_url(redis: Redis, endpoint_id: str) -> str | None:
    token = await redis.get(_endpoint_url_key(endpoint_id))
    if not token:
        return None
    try:
        return decrypt_secret(token)
    except Exception:
        logger.warning("upstream_proxy: failed to decrypt proxy url for endpoint=%s", endpoint_id)
        return None


async def mark_available(redis: Redis, endpoint_id: UUID) -> None:
    await redis.sadd(_available_set_key(), str(endpoint_id))


async def mark_unavailable(redis: Redis, endpoint_id: str) -> None:
    await redis.srem(_available_set_key(), endpoint_id)


async def set_cooldown(redis: Redis, endpoint_id: str, *, cooldown_seconds: int) -> None:
    # Dedicated key with TTL; picking logic avoids ids in cooldown.
    await redis.set(_cooldown_key(endpoint_id), "1", ex=int(cooldown_seconds))


async def in_cooldown(redis: Redis, endpoint_id: str) -> bool:
    try:
        return bool(await redis.exists(_cooldown_key(endpoint_id)))
    except Exception:
        return False


async def pick_available_proxy_id(
    redis: Redis,
    *,
    exclude_ids: set[str] | None = None,
) -> str | None:
    """
    Pick an available proxy endpoint id.

    Notes:
    - exclude_ids is used for request-level retries (avoid using the same proxy twice).
    - We also avoid ids currently in cooldown.
    """
    exclude_ids = exclude_ids or set()

    try:
        if not exclude_ids:
            # Fast path: one random candidate.
            candidate = await redis.srandmember(_available_set_key())
            if not candidate:
                return None
            if await in_cooldown(redis, candidate):
                # Cleanup stale availability quickly.
                await mark_unavailable(redis, candidate)
                return None
            return candidate

        # Slow path: filter.
        all_ids = await redis.smembers(_available_set_key())
        for endpoint_id in all_ids:
            if endpoint_id in exclude_ids:
                continue
            if await in_cooldown(redis, endpoint_id):
                continue
            return endpoint_id
        return None
    except Exception as exc:
        logger.debug("upstream_proxy: pick failed (redis error): %s", exc)
        return None


async def report_failure_by_proxy_url(
    *,
    proxy_url: str,
    cooldown_seconds: int,
) -> None:
    """
    Request-side failure feedback.

    - Looks up endpoint_id via Redis mapping;
    - Removes it from available set and sets a cooldown key.
    """
    try:
        # Import at call-time so tests can monkeypatch app.redis_client.get_redis_client.
        from app.redis_client import get_redis_client

        redis = get_redis_client()
        fp = compute_url_fingerprint(proxy_url)
        endpoint_id = await redis.get(_url_to_id_key(fp))
        if not endpoint_id:
            return
        await mark_unavailable(redis, endpoint_id)
        await set_cooldown(redis, endpoint_id, cooldown_seconds=cooldown_seconds)
    except Exception as exc:
        # Never let observability/feedback break the main request flow.
        logger.debug("upstream_proxy: report_failure skipped (%s)", exc)


__all__ = [
    "clear_runtime_pool",
    "get_endpoint_proxy_url",
    "get_runtime_config",
    "mark_available",
    "mark_unavailable",
    "pick_available_proxy_id",
    "put_endpoint_proxy_url",
    "report_failure_by_proxy_url",
    "set_runtime_config",
]
