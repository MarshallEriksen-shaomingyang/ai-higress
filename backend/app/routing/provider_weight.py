"""
Dynamic provider weight adjustments for routing调度。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from redis.asyncio import Redis

from app.logging_config import logger
from app.schemas import PhysicalModel

# Redis key for storing dynamic weights per logical model.
_WEIGHT_KEY_TEMPLATE = "routing:{logical_model}:provider_weights"

# Clamp factors to avoid runaway weights.
_MIN_FACTOR = 0.2
_MAX_FACTOR = 3.0
_ABSOLUTE_MIN = 0.01

# How strongly to nudge weights on outcomes (relative to base weight).
_SUCCESS_FACTOR = 0.05
_RETRYABLE_FAILURE_FACTOR = -0.2
_FATAL_FAILURE_FACTOR = -0.5


def _redis_key(logical_model_id: str) -> str:
    return _WEIGHT_KEY_TEMPLATE.format(logical_model=logical_model_id)


def _clamp_weight(value: float, base_weight: float) -> float:
    """
    保证动态权重在合理范围内，避免过大或降到 0。
    """
    safe_base = base_weight or 1.0
    lower = max(safe_base * _MIN_FACTOR, _ABSOLUTE_MIN)
    upper = max(safe_base * _MAX_FACTOR, lower)
    return max(min(value, upper), lower)


def clamp_provider_weight(value: float, base_weight: float) -> float:
    """
    对外暴露的权重钳制工具函数，确保权重相对 base_weight 落在合理范围内。
    """
    return _clamp_weight(value, base_weight)


async def load_dynamic_weights(
    redis: Redis | None,
    logical_model_id: str,
    upstreams: Sequence[PhysicalModel],
) -> dict[str, float]:
    """
    读取（或初始化）各厂商的动态权重。
    返回 provider_id -> effective_weight 的映射；若 Redis 不可用则返回空映射。
    """
    if redis is None or not upstreams:
        return {}

    base_map: dict[str, float] = {}
    for up in upstreams:
        # 相同 provider 多个上游取第一个配置值。
        base_map.setdefault(up.provider_id, up.base_weight)

    provider_ids: list[str] = list(base_map.keys())
    key = _redis_key(logical_model_id)

    try:
        # 先写入默认权重（NX 保证不覆盖已有动态值）。
        await redis.zadd(key, base_map, nx=True)
        scores = await redis.zmscore(key, provider_ids)
    except Exception as exc:  # pragma: no cover - Redis 可用性问题不影响主流程
        logger.debug("load_dynamic_weights skipped: %s", exc)
        return {}

    weights: dict[str, float] = {}
    for pid, raw in zip(provider_ids, scores):
        base_weight = base_map[pid]
        if raw is None:
            weights[pid] = base_weight
            continue

        clamped = _clamp_weight(float(raw), base_weight)
        weights[pid] = clamped
        if clamped != raw:
            await redis.zadd(key, {pid: clamped})

    return weights


async def adjust_provider_weight(
    redis: Redis | None,
    logical_model_id: str,
    provider_id: str,
    *,
    base_weight: float,
    delta: float,
) -> None:
    """
    调整指定 provider 的动态权重，带上下限保护。
    """
    if redis is None:
        return

    safe_base = base_weight or 1.0
    key = _redis_key(logical_model_id)
    try:
        await redis.zadd(key, {provider_id: safe_base}, nx=True)
        updated = await redis.zincrby(key, delta, provider_id)
        clamped = _clamp_weight(float(updated), safe_base)
        if clamped != updated:
            await redis.zadd(key, {provider_id: clamped})
    except Exception as exc:  # pragma: no cover - 不影响主流程
        logger.debug(
            "provider weight update skipped for %s/%s: %s",
            logical_model_id,
            provider_id,
            exc,
        )


def record_provider_success(
    redis: Redis | None,
    logical_model_id: str,
    provider_id: str,
    base_weight: float,
) -> None:
    """
    异步上调成功厂商的权重（轻微增加）。
    """
    if redis is None:
        return
    delta = max(base_weight * _SUCCESS_FACTOR, _ABSOLUTE_MIN)
    asyncio.create_task(
        adjust_provider_weight(
            redis,
            logical_model_id,
            provider_id,
            base_weight=base_weight,
            delta=delta,
        )
    )


def record_provider_failure(
    redis: Redis | None,
    logical_model_id: str,
    provider_id: str,
    base_weight: float,
    *,
    retryable: bool,
) -> None:
    """
    异步下调失败厂商的权重，非重试错误下降幅度更大。
    """
    if redis is None:
        return

    factor = _RETRYABLE_FAILURE_FACTOR if retryable else _FATAL_FAILURE_FACTOR
    delta = base_weight * factor
    asyncio.create_task(
        adjust_provider_weight(
            redis,
            logical_model_id,
            provider_id,
            base_weight=base_weight,
            delta=delta,
        )
    )


async def invalidate_provider_weights(
    redis: Redis | None,
    logical_model_id: str,
    provider_ids: Sequence[str] | None = None,
) -> None:
    """清除指定逻辑模型下的动态权重缓存。"""

    if redis is None:
        return

    key = _redis_key(logical_model_id)
    try:
        if not provider_ids:
            await redis.delete(key)
            return

        unique_ids = [pid for pid in dict.fromkeys(provider_ids) if pid]
        if not unique_ids:
            return

        await redis.zrem(key, *unique_ids)
        remaining = await redis.zcard(key)
        if remaining == 0:
            await redis.delete(key)
    except Exception as exc:  # pragma: no cover - 不影响主流程
        logger.debug(
            "invalidate provider weights skipped for %s (%s): %s",
            logical_model_id,
            provider_ids,
            exc,
        )


__all__ = [
    "adjust_provider_weight",
    "clamp_provider_weight",
    "invalidate_provider_weights",
    "load_dynamic_weights",
    "record_provider_failure",
    "record_provider_success",
]
