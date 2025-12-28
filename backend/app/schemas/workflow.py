from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowToolConfig(BaseModel):
    agent_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int | None = Field(default=None, ge=1)
    stream: bool | None = None


class WorkflowStep(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: Literal["tool_call"] = "tool_call"
    tool_config: WorkflowToolConfig
    approval_policy: Literal["manual", "auto"] = "auto"
    on_error: Literal["stop", "continue"] = "stop"


class WorkflowSpec(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    variables: dict[str, Any] | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)


class WorkflowCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    spec: WorkflowSpec


class WorkflowResponse(BaseModel):
    workflow_id: UUID
    title: str
    description: str | None
    spec: WorkflowSpec
    created_at: str
    updated_at: str


class WorkflowRunCreateRequest(BaseModel):
    workflow_id: UUID


class WorkflowRunResumeRequest(BaseModel):
    # v0：resume 默认表示“恢复/继续”；若当前 paused_reason=awaiting_approval，则等价于 approve 当前 step。
    pass


class WorkflowRunCancelRequest(BaseModel):
    reason: str | None = None


class WorkflowRunResponse(BaseModel):
    run_id: UUID
    workflow_id: UUID | None
    status: str
    paused_reason: str | None
    current_step_index: int
    workflow_snapshot: WorkflowSpec
    steps_state: dict[str, Any]
    created_at: str
    updated_at: str


__all__ = [
    "WorkflowCreateRequest",
    "WorkflowResponse",
    "WorkflowRunCancelRequest",
    "WorkflowRunCreateRequest",
    "WorkflowRunResponse",
    "WorkflowRunResumeRequest",
    "WorkflowSpec",
    "WorkflowStep",
    "WorkflowToolConfig",
]
