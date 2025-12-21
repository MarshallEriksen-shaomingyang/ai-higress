from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .evals import EvalExplanation


class AdminRunSummary(BaseModel):
    """
    管理员视角的 Run 摘要信息。

    注意：为了隐私合规，不返回 output_text/output_preview 以及任何聊天内容字段。
    """

    run_id: UUID
    requested_logical_model: str
    status: str
    selected_provider_id: str | None = None
    selected_provider_model: str | None = None
    latency_ms: int | None = None
    cost_credits: int | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminEvalRatingInfo(BaseModel):
    winner_run_id: UUID
    reason_tags: list[str] = Field(default_factory=list)
    created_at: datetime


class AdminEvalItem(BaseModel):
    eval_id: UUID
    status: str
    project_id: UUID
    assistant_id: UUID
    baseline_run_id: UUID
    baseline_run: AdminRunSummary | None = None
    challengers: list[AdminRunSummary] = Field(default_factory=list)
    explanation: EvalExplanation | None = None
    rated_at: datetime | None = None
    rating: AdminEvalRatingInfo | None = None
    created_at: datetime
    updated_at: datetime


class AdminEvalListResponse(BaseModel):
    items: list[AdminEvalItem] = Field(default_factory=list)
    next_cursor: str | None = None


__all__ = [
    "AdminEvalItem",
    "AdminEvalListResponse",
    "AdminEvalRatingInfo",
    "AdminRunSummary",
]

