"""
High-level Redis helpers for the multi-provider routing layer.

This module encapsulates the key patterns defined in
specs/001-model-routing/data-model.md so that the rest of the codebase
does not have to deal with raw Redis keys directly.
"""

from __future__ import annotations

from typing import Any

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.schemas import LogicalModel, MetricsHistory, RoutingMetrics, Session
from app.redis_client import redis_get_json, redis_set_json

# Key templates (must match data-model.md).
PROVIDER_MODELS_KEY_TEMPLATE = "llm:vendor:{provider_id}:models"
LOGICAL_MODEL_KEY_TEMPLATE = "llm:logical:{logical_model}"
METRICS_KEY_TEMPLATE = "llm:metrics:{logical_model}:{provider_id}"
SESSION_KEY_TEMPLATE = "llm:session:{conversation_id}"
METRICS_HISTORY_KEY_TEMPLATE = (
    "llm:metrics:history:{logical_model}:{provider_id}:{timestamp}"
)


async def get_provider_models_json(
    redis: Redis, provider_id: str
) -> list[dict[str, Any]] | None:
    """
    Return the raw JSON list of models for a provider, or None.
    """
    key = PROVIDER_MODELS_KEY_TEMPLATE.format(provider_id=provider_id)
    data = await redis_get_json(redis, key)
    if data is None:
        return None
    if isinstance(data, list):
        return data
    # Malformed payload; treat as missing.
    return None


async def set_provider_models(
    redis: Redis,
    provider_id: str,
    models: list[Any],
    *,
    ttl_seconds: int,
) -> None:
    """
    Store provider models list into Redis with the given TTL.
    `models` should be JSON-serialisable (dicts or Pydantic models).
    """
    key = PROVIDER_MODELS_KEY_TEMPLATE.format(provider_id=provider_id)
    serialisable: list[Any] = []
    for m in models:
        if hasattr(m, "model_dump"):
            serialisable.append(m.model_dump())
        else:
            serialisable.append(m)
    await redis_set_json(redis, key, serialisable, ttl_seconds=ttl_seconds)


async def get_logical_model(redis: Redis, logical_model_id: str) -> LogicalModel | None:
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical_model_id)
    data = await redis_get_json(redis, key)
    if not data:
        return None
    return LogicalModel.model_validate(data)


async def set_logical_model(
    redis: Redis, logical_model: LogicalModel
) -> None:
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical_model.logical_id)
    await redis_set_json(redis, key, logical_model.model_dump(), ttl_seconds=None)


async def delete_logical_model(redis: Redis, logical_model_id: str) -> int:
    """
    删除指定的逻辑模型键，返回删除的键数量（0/1）。
    """

    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical_model_id)
    return int(await redis.delete(key))  # type: ignore[attr-defined]


async def list_logical_models(redis: Redis) -> list[LogicalModel]:
    """
    List all logical models stored under llm:logical:*.
    This uses a simple KEYS-based scan for now; it can be refined to SCAN
    if the keyspace grows large.
    """
    pattern = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model="*")
    keys = await redis.keys(pattern)  # type: ignore[attr-defined]
    models: list[LogicalModel] = []
    for key in keys:
        data = await redis_get_json(redis, key)
        if not data:
            continue
        try:
            models.append(LogicalModel.model_validate(data))
        except Exception:
            # Skip malformed entries; callers can inspect logs separately
            continue
    return models


async def get_routing_metrics(
    redis: Redis, logical_model_id: str, provider_id: str
) -> RoutingMetrics | None:
    key = METRICS_KEY_TEMPLATE.format(
        logical_model=logical_model_id, provider_id=provider_id
    )
    data = await redis_get_json(redis, key)
    if not data:
        return None
    return RoutingMetrics.model_validate(data)


async def set_routing_metrics(
    redis: Redis, metrics: RoutingMetrics, *, ttl_seconds: int = 3600
) -> None:
    key = METRICS_KEY_TEMPLATE.format(
        logical_model=metrics.logical_model, provider_id=metrics.provider_id
    )
    await redis_set_json(redis, key, metrics.model_dump(), ttl_seconds=ttl_seconds)


async def append_metrics_history(
    redis: Redis, sample: MetricsHistory, *, ttl_seconds: int = 86400 * 7
) -> None:
    key = METRICS_HISTORY_KEY_TEMPLATE.format(
        logical_model=sample.logical_model,
        provider_id=sample.provider_id,
        timestamp=int(sample.timestamp),
    )
    await redis_set_json(redis, key, sample.model_dump(), ttl_seconds=ttl_seconds)


async def get_session(redis: Redis, conversation_id: str) -> Session | None:
    key = SESSION_KEY_TEMPLATE.format(conversation_id=conversation_id)
    data = await redis_get_json(redis, key)
    if not data:
        return None
    return Session.model_validate(data)


async def set_session(
    redis: Redis, session: Session, *, ttl_seconds: int = 7200
) -> None:
    key = SESSION_KEY_TEMPLATE.format(conversation_id=session.conversation_id)
    await redis_set_json(redis, key, session.model_dump(), ttl_seconds=ttl_seconds)


__all__ = [
    "LOGICAL_MODEL_KEY_TEMPLATE",
    "METRICS_HISTORY_KEY_TEMPLATE",
    "METRICS_KEY_TEMPLATE",
    "PROVIDER_MODELS_KEY_TEMPLATE",
    "SESSION_KEY_TEMPLATE",
    "append_metrics_history",
    "get_logical_model",
    "get_provider_models_json",
    "get_routing_metrics",
    "get_session",
    "set_logical_model",
    "delete_logical_model",
    "list_logical_models",
    "set_provider_models",
    "set_routing_metrics",
    "set_session",
]
