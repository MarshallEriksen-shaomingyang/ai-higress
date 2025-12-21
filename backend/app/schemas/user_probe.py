from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProbeApiStyle = Literal["auto", "openai", "claude", "responses"]


class UserProbeTaskCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    model_id: str = Field(..., min_length=1, max_length=200, description="探针使用的模型 ID")
    prompt: str = Field(..., min_length=1, max_length=2000, description="探针提示词")
    interval_seconds: int = Field(..., ge=60, description="探针执行间隔（秒）")
    max_tokens: int | None = Field(default=None, ge=1, description="最大输出 token 数（可选）")
    api_style: ProbeApiStyle = Field(default="auto", description="上游 API 风格：auto/openai/claude/responses")
    enabled: bool = Field(default=True, description="是否启用任务")


class UserProbeTaskUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    model_id: str | None = Field(default=None, min_length=1, max_length=200)
    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    interval_seconds: int | None = Field(default=None, ge=60)
    max_tokens: int | None = Field(default=None, ge=1)
    api_style: ProbeApiStyle | None = None
    enabled: bool | None = None


class UserProbeRunResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    provider_id: str
    model_id: str
    api_style: str
    success: bool
    status_code: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None
    response_text: str | None = None
    response_excerpt: str | None = None
    response_json: Any | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProbeTaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    provider_id: str
    name: str
    model_id: str
    prompt: str
    interval_seconds: int
    max_tokens: int
    api_style: str
    enabled: bool
    in_progress: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_run: UserProbeRunResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "ProbeApiStyle",
    "UserProbeRunResponse",
    "UserProbeTaskCreateRequest",
    "UserProbeTaskResponse",
    "UserProbeTaskUpdateRequest",
]

