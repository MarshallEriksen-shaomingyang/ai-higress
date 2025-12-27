from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.models import Provider
from app.provider.health import HealthStatus
from app.repositories.provider_health_repository import (
    apply_health_status as repo_apply_health_status,
    get_provider_by_provider_id as repo_get_provider_by_provider_id,
)
from app.redis_client import redis_get_json, redis_set_json
from app.schemas import ProviderStatus
from app.settings import settings

if TYPE_CHECKING:  # pragma: no cover - typing hint only
    from redis.asyncio import Redis
else:  # pragma: no cover - fallback type when redis isn't installed
    Redis = Any


HEALTH_STATUS_KEY_TEMPLATE = "llm:provider:health:{provider_id}"


async def cache_health_status(
    redis: Redis, status: HealthStatus, *, ttl_seconds: int | None = None
) -> None:
    key = HEALTH_STATUS_KEY_TEMPLATE.format(provider_id=status.provider_id)
    await redis_set_json(redis, key, status.model_dump(), ttl_seconds=ttl_seconds)


async def get_cached_health_status(redis: Redis, provider_id: str) -> HealthStatus | None:
    key = HEALTH_STATUS_KEY_TEMPLATE.format(provider_id=provider_id)
    data = await redis_get_json(redis, key)
    if not data:
        return None
    try:
        return HealthStatus.model_validate(data)
    except Exception:
        return None


def _convert_metadata(metadata: dict[str, Any] | None, key: str) -> Any:
    if not metadata:
        return None
    return metadata.get(key)


def _provider_to_health_status(provider: Provider) -> HealthStatus | None:
    """
    将 Provider ORM 实体转换为 HealthStatus。

    这里有一个额外的兼容逻辑：
    - 当 provider 记录存在但尚未写入 last_check（从未跑过健康检查）时，
      之前实现会返回 None，导致上层 /providers/{id}/health 直接返回 404，
      给人一种「Provider 不存在」的误导。
    - 为避免这种歧义，我们现在对这类情况也返回一个默认的健康状态：
      使用 provider.status 作为当前状态，时间戳优先取 last_check，
      若为空则退回 created_at，再退回当前时间。
    """
    if provider is None:
        return None

    metadata: dict[str, Any] | None = provider.metadata_json or None
    try:
        status = ProviderStatus(provider.status)
    except Exception:
        status = ProviderStatus.DOWN

    # 优先使用最近一次健康检查时间；如果还没有检查过，则使用创建时间，
    # 再退回到当前时间，避免因为 last_check 为空而让上层误判为「不存在」。
    timestamp = provider.last_check or getattr(provider, "created_at", None)
    if timestamp is None:
        timestamp = datetime.now(UTC)

    return HealthStatus(
        provider_id=provider.provider_id,
        status=status,
        timestamp=timestamp.timestamp(),
        response_time_ms=_convert_metadata(metadata, "response_time_ms"),
        error_message=_convert_metadata(metadata, "error_message"),
        last_successful_check=_convert_metadata(metadata, "last_successful_check"),
    )


async def get_health_status_with_fallback(
    redis: Redis, session: Session, provider_id: str
) -> HealthStatus | None:
    cached = await get_cached_health_status(redis, provider_id)
    if cached is not None:
        return cached

    provider = repo_get_provider_by_provider_id(session, provider_id=provider_id)
    if provider is None:
        return None

    return _provider_to_health_status(provider)


async def persist_provider_health(
    redis: Redis,
    session: Session,
    provider: Provider,
    status: HealthStatus,
    *,
    cache_ttl_seconds: int | None = None,
) -> None:
    repo_apply_health_status(session, provider=provider, status=status)

    ttl = cache_ttl_seconds or settings.provider_health_cache_ttl_seconds
    await cache_health_status(redis, status, ttl_seconds=ttl)


__all__ = [
    "HEALTH_STATUS_KEY_TEMPLATE",
    "cache_health_status",
    "get_cached_health_status",
    "get_health_status_with_fallback",
    "persist_provider_health",
]
