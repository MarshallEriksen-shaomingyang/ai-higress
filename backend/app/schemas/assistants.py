from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.image import ImageGenerationRequest


class AssistantPresetCreateRequest(BaseModel):
    project_id: UUID | None = Field(default=None, description="MVP: project_id == api_key_id，可为空")
    name: str = Field(..., min_length=1, max_length=120)
    system_prompt: str = Field(default="", max_length=20000)
    default_logical_model: str = Field(..., min_length=1, max_length=128)
    title_logical_model: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="会话标题生成模型；为空表示跟随 default_logical_model",
    )
    model_preset: dict | None = None

    model_config = ConfigDict(extra="forbid")


class AssistantPresetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_prompt: str | None = Field(default=None, max_length=20000)
    default_logical_model: str | None = Field(default=None, min_length=1, max_length=128)
    title_logical_model: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="会话标题生成模型；为空表示跟随 default_logical_model",
    )
    model_preset: dict | None = None
    archived: bool | None = None

    model_config = ConfigDict(extra="forbid")


class AssistantPresetItem(BaseModel):
    assistant_id: UUID
    project_id: UUID | None = None
    name: str
    system_prompt: str = Field(default="", max_length=20000)
    default_logical_model: str
    title_logical_model: str | None = None
    created_at: datetime
    updated_at: datetime


class AssistantPresetResponse(AssistantPresetItem):
    model_preset: dict | None = None
    archived_at: datetime | None = None


class PaginatedResponse(BaseModel):
    next_cursor: str | None = None


class AssistantPresetListResponse(PaginatedResponse):
    items: list[AssistantPresetItem] = Field(default_factory=list)


class ConversationCreateRequest(BaseModel):
    assistant_id: UUID
    project_id: UUID = Field(..., description="MVP: project_id == api_key_id")
    title: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    archived: bool | None = None
    is_pinned: bool | None = None
    unread_count: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class ConversationItem(BaseModel):
    conversation_id: UUID
    assistant_id: UUID
    project_id: UUID
    title: str | None = None
    last_activity_at: datetime
    archived_at: datetime | None = None
    is_pinned: bool = False
    last_message_content: str | None = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(PaginatedResponse):
    items: list[ConversationItem] = Field(default_factory=list)


class BridgeToolSelection(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    tool_names: list[str] = Field(..., min_length=1, max_length=30)

    model_config = ConfigDict(extra="forbid")


class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=20000)
    override_logical_model: str | None = Field(default=None, min_length=1, max_length=128)
    model_preset: dict | None = None
    bridge_agent_id: str | None = Field(default=None, min_length=1, max_length=128)
    bridge_agent_ids: list[str] | None = Field(default=None, max_length=5)
    # 可选：指定每个 Agent 的工具子集；若不传则使用 Agent 的全部工具。
    bridge_tool_selections: list[BridgeToolSelection] | None = Field(default=None, max_length=5)
    streaming: bool = Field(default=False)

    model_config = ConfigDict(extra="forbid")


class MessageCreateResponse(BaseModel):
    message_id: UUID
    baseline_run: RunSummary


class MessageRegenerateResponse(BaseModel):
    assistant_message_id: UUID
    baseline_run: RunSummary


class MessageRegenerateRequest(BaseModel):
    override_logical_model: str | None = Field(default=None, min_length=1, max_length=128)
    model_preset: dict | None = None
    bridge_agent_id: str | None = Field(default=None, min_length=1, max_length=128)
    bridge_agent_ids: list[str] | None = Field(default=None, max_length=5)
    bridge_tool_selections: list[BridgeToolSelection] | None = Field(default=None, max_length=5)

    model_config = ConfigDict(extra="forbid")


class RunSummary(BaseModel):
    run_id: UUID
    requested_logical_model: str
    status: str
    output_preview: str | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    tool_invocations: list[dict[str, Any]] = Field(default_factory=list)


class MessageItem(BaseModel):
    message_id: UUID
    role: str
    content: dict
    created_at: datetime
    runs: list[RunSummary] = Field(default_factory=list)


class MessageListResponse(PaginatedResponse):
    items: list[MessageItem] = Field(default_factory=list)


class ConversationImageGenerationRequest(ImageGenerationRequest):
    """
    Chat 应用侧的“会话内文生图”请求。

    说明：
    - JWT 鉴权（而非 X-API-Key）；
    - 结果会写入会话历史（chat_messages），用于“历史记录/回放/多端同步”；
    - 默认 response_format=url（走 OSS + /media/images 短链），避免把大体积 base64 写入历史。
    """

    prompt: str = Field(..., min_length=1, max_length=20000)
    model: str = Field(..., min_length=1, max_length=128)
    streaming: bool = Field(default=False, description="是否使用 SSE 推送生成状态与最终结果")

    model_config = ConfigDict(extra="forbid")


class RunDetailResponse(RunSummary):
    message_id: UUID
    selected_provider_id: str | None = None
    selected_provider_model: str | None = None
    output_text: str | None = None
    request_payload: dict | None = None
    response_payload: dict | None = None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AssistantPresetCreateRequest",
    "AssistantPresetItem",
    "AssistantPresetListResponse",
    "AssistantPresetResponse",
    "AssistantPresetUpdateRequest",
    "ConversationCreateRequest",
    "ConversationItem",
    "ConversationListResponse",
    "ConversationUpdateRequest",
    "MessageCreateRequest",
    "MessageCreateResponse",
    "MessageRegenerateResponse",
    "MessageItem",
    "MessageListResponse",
    "ConversationImageGenerationRequest",
    "RunDetailResponse",
    "RunSummary",
]
