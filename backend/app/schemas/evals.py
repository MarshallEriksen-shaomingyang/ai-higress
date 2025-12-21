from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .assistants import RunSummary


class EvalCreateRequest(BaseModel):
    project_id: UUID
    assistant_id: UUID
    conversation_id: UUID
    message_id: UUID
    baseline_run_id: UUID
    streaming: bool = Field(default=False)

    model_config = ConfigDict(extra="forbid")


class EvalChallengerItem(RunSummary):
    pass


class EvalExplanation(BaseModel):
    summary: str
    evidence: dict | None = None


class EvalResponse(BaseModel):
    eval_id: UUID
    status: str
    baseline_run_id: UUID
    challengers: list[EvalChallengerItem] = Field(default_factory=list)
    explanation: EvalExplanation | None = None
    created_at: datetime
    updated_at: datetime


class EvalRatingRequest(BaseModel):
    winner_run_id: UUID
    reason_tags: list[str] = Field(default_factory=list, max_length=10)

    model_config = ConfigDict(extra="forbid")


class EvalRatingResponse(BaseModel):
    eval_id: UUID
    winner_run_id: UUID
    reason_tags: list[str] = Field(default_factory=list)
    created_at: datetime


__all__ = [
    "EvalChallengerItem",
    "EvalCreateRequest",
    "EvalExplanation",
    "EvalRatingRequest",
    "EvalRatingResponse",
    "EvalResponse",
]

