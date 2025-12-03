from __future__ import annotations

import time
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.auth import require_api_key
from app.deps import get_redis
from app.errors import not_found, service_unavailable
from app.schemas import (
    LogicalModel,
    PhysicalModel,
    RoutingMetrics,
    SchedulingStrategy,
    Session,
)
from app.routing.mapper import select_candidate_upstreams
from app.routing.provider_weight import load_dynamic_weights
from app.routing.scheduler import choose_upstream
from app.routing.session_manager import bind_session, get_session
from app.storage.redis_service import get_logical_model, get_routing_metrics

router = APIRouter(
    tags=["routing"],
    dependencies=[Depends(require_api_key)],
)


class RoutingRequest(BaseModel):
    logical_model: str = Field(..., description="Logical model id")
    conversation_id: str | None = Field(
        default=None, description="Conversation id for stickiness"
    )
    user_id: str | None = Field(default=None, description="User id (unused for now)")
    preferred_region: str | None = Field(
        default=None, description="Preferred region for upstream selection"
    )
    strategy: str | None = Field(
        default=None,
        description="Strategy name (latency_first/cost_first/reliability_first/balanced)",
    )
    exclude_providers: list[str] | None = Field(
        default=None, description="Optional list of provider ids to exclude"
    )


class CandidateInfo(BaseModel):
    upstream: PhysicalModel
    score: float
    metrics: RoutingMetrics | None = None


class RoutingDecision(BaseModel):
    logical_model: str
    selected_upstream: PhysicalModel
    decision_time: float
    reasoning: str
    alternative_upstreams: list[PhysicalModel] | None = None
    strategy_used: str | None = None
    all_candidates: list[CandidateInfo] | None = None


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

    strategy = _strategy_from_name(body.strategy)

    # Optional session stickiness.
    session: Session | None = None
    if body.conversation_id:
        session = await get_session(redis, body.conversation_id)

    metrics_by_provider = await _load_metrics_for_candidates(
        redis, logical.logical_id, candidates
    )
    dynamic_weights = await load_dynamic_weights(
        redis, logical.logical_id, candidates
    )
    try:
        selected, scored = choose_upstream(
            logical,
            candidates,
            metrics_by_provider,
            strategy,
            session=session,
            dynamic_weights=dynamic_weights,
        )
    except RuntimeError as exc:
        raise service_unavailable(str(exc))

    # Bind session if requested and enabled.
    if body.conversation_id and strategy.enable_stickiness:
        await bind_session(
            redis,
            conversation_id=body.conversation_id,
            logical_model=logical.logical_id,
            provider_id=selected.upstream.provider_id,
            model_id=selected.upstream.model_id,
        )

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
