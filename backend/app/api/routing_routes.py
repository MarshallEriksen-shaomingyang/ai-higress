from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_redis
from app.errors import not_found, service_unavailable
from app.jwt_auth import require_jwt_token
from app.routing.mapper import select_candidate_upstreams
from app.routing.provider_weight import load_dynamic_weights
from app.routing.scheduler import choose_upstream
from app.schemas import LogicalModel, PhysicalModel, RoutingMetrics, SchedulingStrategy
from app.schemas.routing import CandidateInfo, RoutingDecision, RoutingRequest
from app.services.provider_health_service import get_cached_health_status
from app.settings import settings
from app.storage.redis_service import get_logical_model, get_routing_metrics

router = APIRouter(
    tags=["routing"],
    dependencies=[Depends(require_jwt_token)],
)


def _status_worse(a, b) -> bool:
    order = {"healthy": 0, "degraded": 1, "down": 2}
    return order.get(getattr(b, "value", str(b)), 0) > order.get(getattr(a, "value", str(a)), 0)


def _strategy_from_name(name: str | None) -> SchedulingStrategy:
    """
    Map a simple strategy name to a SchedulingStrategy instance.
    For now, all strategies share the same weights; this can be tuned later.
    """
    base = SchedulingStrategy(
        name=name or "balanced",
        description="Default routing strategy",
    )
    if name == "latency_first":
        base.alpha = 0.6
        base.beta = 0.2
        base.gamma = 0.1
        base.delta = 0.1
    elif name == "cost_first":
        base.alpha = 0.2
        base.beta = 0.2
        base.gamma = 0.5
        base.delta = 0.1
    elif name == "reliability_first":
        base.alpha = 0.3
        base.beta = 0.5
        base.gamma = 0.1
        base.delta = 0.1
    return base


async def _load_metrics_for_candidates(
    redis: Redis, logical_model_id: str, upstreams: Sequence[PhysicalModel]
) -> dict[str, RoutingMetrics]:
    """
    Load RoutingMetrics for each provider used by the candidate upstreams.
    """
    seen_providers: dict[str, RoutingMetrics] = {}
    for up in upstreams:
        if up.provider_id in seen_providers:
            continue
        metrics = await get_routing_metrics(redis, logical_model_id, up.provider_id)
        if metrics is not None:
            seen_providers[up.provider_id] = metrics
    return seen_providers


@router.post("/routing/decide", response_model=RoutingDecision)
async def decide_route(
    body: RoutingRequest,
    redis: Redis = Depends(get_redis),
) -> RoutingDecision:
    """
    Compute a routing decision for a logical model request.
    """
    start_ts = time.perf_counter()

    logical: LogicalModel | None = await get_logical_model(
        redis, body.logical_model
    )
    if logical is None:
        raise not_found(f"Logical model '{body.logical_model}' not found")

    if not logical.enabled:
        raise service_unavailable(
            f"Logical model '{body.logical_model}' is disabled"
        )

    candidates = select_candidate_upstreams(
        logical,
        preferred_region=body.preferred_region,
        exclude_providers=body.exclude_providers or [],
    )
    if not candidates:
        raise service_unavailable(
            f"No upstreams available for logical model '{body.logical_model}'"
        )

    # Optional: filter candidates based on cached provider health (Redis).
    # This prevents obvious "down" providers from being selected and can reduce
    # tail latency by avoiding retry loops.
    health_by_provider: dict[str, Any] = {}
    if settings.enable_provider_health_check:
        down_providers: set[str] = set()
        for cand in candidates:
            health = await get_cached_health_status(redis, cand.provider_id)
            if health is None:
                continue
            health_by_provider[cand.provider_id] = health
            if health.status.value == "down":
                down_providers.add(cand.provider_id)

        if down_providers:
            filtered = [cand for cand in candidates if cand.provider_id not in down_providers]
            if filtered:
                candidates = filtered

    strategy = _strategy_from_name(body.strategy)

    metrics_by_provider = await _load_metrics_for_candidates(
        redis, logical.logical_id, candidates
    )
    if settings.enable_provider_health_check and health_by_provider:
        active_provider_ids = {c.provider_id for c in candidates}
        for pid, health in health_by_provider.items():
            if pid not in active_provider_ids:
                continue
            existing = metrics_by_provider.get(pid)
            if existing is None:
                latency_ms = float(getattr(health, "response_time_ms", None) or 2000.0)
                metrics_by_provider[pid] = RoutingMetrics(
                    logical_model=logical.logical_id,
                    provider_id=pid,
                    latency_p95_ms=max(1.0, latency_ms),
                    latency_p99_ms=max(1.0, latency_ms * 1.25),
                    error_rate=0.0,
                    success_qps_1m=0.0,
                    total_requests_1m=0,
                    last_updated=float(getattr(health, "timestamp", 0.0) or 0.0),
                    status=health.status,
                )
            else:
                if _status_worse(existing.status, health.status):
                    metrics_by_provider[pid] = existing.model_copy(update={"status": health.status})
    dynamic_weights = await load_dynamic_weights(
        redis, logical.logical_id, candidates
    )
    try:
        selected, scored = choose_upstream(
            logical,
            candidates,
            metrics_by_provider,
            strategy,
            dynamic_weights=dynamic_weights,
            enable_health_check=settings.enable_provider_health_check,
        )
    except RuntimeError as exc:
        raise service_unavailable(str(exc))

    decision_time_ms = (time.perf_counter() - start_ts) * 1000.0

    alternatives = [c.upstream for c in scored if c.upstream != selected.upstream]
    candidate_infos = [
        CandidateInfo(upstream=c.upstream, score=c.score, metrics=c.metrics)
        for c in scored
    ]

    reasoning = (
        f"Selected provider '{selected.upstream.provider_id}' model "
        f"'{selected.upstream.model_id}' for logical model '{logical.logical_id}'."
    )

    return RoutingDecision(
        logical_model=logical.logical_id,
        selected_upstream=selected.upstream,
        decision_time=decision_time_ms,
        reasoning=reasoning,
        alternative_upstreams=alternatives or None,
        strategy_used=strategy.name,
        all_candidates=candidate_infos or None,
    )


__all__ = ["router"]
