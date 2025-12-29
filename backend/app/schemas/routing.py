from pydantic import BaseModel, Field

from .logical_model import PhysicalModel
from .routing_metrics import RoutingMetrics


class RoutingRequest(BaseModel):
    logical_model: str = Field(..., description="Logical model id")
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


__all__ = ["CandidateInfo", "RoutingDecision", "RoutingRequest"]
