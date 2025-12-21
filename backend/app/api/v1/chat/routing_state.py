"""
路由状态门面（v2）

目标：把路由相关的状态与缓存细节（Redis key、探针健康、动态权重、失败冷却）集中管理，
上层模块（selector/executor/route）只依赖该接口，不直接触碰 Redis key 或权重算法实现。
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from app.logging_config import logger
from app.routing.provider_weight import load_dynamic_weights, record_provider_failure, record_provider_success
from app.schemas import PhysicalModel, RoutingMetrics
from app.services.provider_health_service import get_cached_health_status
from app.settings import settings
from app.storage.redis_service import get_routing_metrics

FAILURE_KEY_PREFIX = "provider:failure:"


@dataclass(frozen=True)
class FailureCooldownStatus:
    provider_id: str
    count: int
    threshold: int
    cooldown_seconds: int
    should_skip: bool


class RoutingStateService:
    """
    路由状态门面：统一维护/读取路由相关缓存与策略。

    包含：
    - Provider 健康缓存（探针写入）
    - 路由指标（metrics）
    - 动态权重（升权/降权）
    - 执行阶段失败冷却（快速熔断）
    """

    def __init__(self, *, redis: Redis):
        self.redis = redis

    async def get_cached_health_status(self, provider_id: str):
        if not settings.enable_provider_health_check:
            return None
        try:
            return await get_cached_health_status(self.redis, provider_id)
        except Exception:  # pragma: no cover - Redis 可用性问题不影响主流程
            return None

    async def get_routing_metrics(
        self, logical_model_id: str, provider_id: str
    ) -> RoutingMetrics | None:
        try:
            return await get_routing_metrics(self.redis, logical_model_id, provider_id)
        except Exception:  # pragma: no cover
            return None

    async def load_metrics_for_candidates(
        self, logical_model_id: str, upstreams: list[PhysicalModel]
    ) -> dict[str, RoutingMetrics]:
        metrics_by_provider: dict[str, RoutingMetrics] = {}
        for up in upstreams:
            if up.provider_id in metrics_by_provider:
                continue
            metrics = await self.get_routing_metrics(logical_model_id, up.provider_id)
            if metrics is not None:
                metrics_by_provider[up.provider_id] = metrics
        return metrics_by_provider

    async def load_dynamic_weights(
        self, logical_model_id: str, upstreams: list[PhysicalModel]
    ) -> dict[str, float]:
        try:
            return await load_dynamic_weights(self.redis, logical_model_id, upstreams)
        except Exception:  # pragma: no cover
            return {}

    def record_success(self, logical_model_id: str, provider_id: str, base_weight: float) -> None:
        record_provider_success(self.redis, logical_model_id, provider_id, base_weight)

    def record_failure(
        self,
        logical_model_id: str,
        provider_id: str,
        base_weight: float,
        *,
        retryable: bool,
    ) -> None:
        record_provider_failure(
            self.redis, logical_model_id, provider_id, base_weight, retryable=retryable
        )

    async def get_failure_cooldown_status(self, provider_id: str) -> FailureCooldownStatus:
        threshold = int(settings.provider_failure_threshold)
        cooldown = int(settings.provider_failure_cooldown_seconds)
        if threshold <= 0:
            return FailureCooldownStatus(
                provider_id=provider_id,
                count=0,
                threshold=threshold,
                cooldown_seconds=cooldown,
                should_skip=False,
            )

        failure_key = f"{FAILURE_KEY_PREFIX}{provider_id}"
        try:
            raw = await self.redis.get(failure_key)
            count = int(raw) if raw else 0
        except Exception:
            count = 0
        return FailureCooldownStatus(
            provider_id=provider_id,
            count=count,
            threshold=threshold,
            cooldown_seconds=cooldown,
            should_skip=count >= threshold,
        )

    async def increment_provider_failure(self, provider_id: str) -> int:
        failure_key = f"{FAILURE_KEY_PREFIX}{provider_id}"
        try:
            count = await self.redis.incr(failure_key)
            await self.redis.expire(
                failure_key, int(settings.provider_failure_cooldown_seconds)
            )
            return int(count)
        except Exception:  # pragma: no cover
            logger.exception("Failed to increment provider failure count for %s", provider_id)
            return 0

    async def clear_provider_failure(self, provider_id: str) -> None:
        failure_key = f"{FAILURE_KEY_PREFIX}{provider_id}"
        try:
            await self.redis.delete(failure_key)
        except Exception:  # pragma: no cover
            logger.exception("Failed to clear provider failure flag for %s", provider_id)


__all__ = ["FailureCooldownStatus", "RoutingStateService"]

