from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MemoryScope = Literal["none", "user", "system"]
StructuredScope = Literal["user", "project"]
StructuredOpType = Literal["UPSERT"]


class MemoryItem(BaseModel):
    content: str = Field(..., min_length=1, description="独立陈述句（已去上下文）")
    category: str = Field(..., min_length=1, description="记忆分类标签（用于检索过滤）")
    keywords: list[str] = Field(default_factory=list, description="关键词列表（用于检索过滤）")


class StructuredOp(BaseModel):
    op: StructuredOpType = Field(..., description="结构化操作类型（MVP: UPSERT）")
    scope: StructuredScope = Field(..., description="结构化属性作用域（user: 用户偏好；project: 项目约束）")
    category: str = Field(..., min_length=1, description="分类（preference|constraint）")
    key: str = Field(..., min_length=1, description="稳定 key（dotted path）")
    value: object = Field(..., description="JSON 值（string/number/bool/object/array）")
    confidence: float | None = Field(default=None, description="可选置信度（0-1）")
    reason: str | None = Field(default=None, description="可选：提取理由（便于灰测/调参）")


class ProjectMemoryRouteDryRunRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="最近对话片段（user/assistant 交错文本）")
    router_logical_model: str | None = Field(default=None, min_length=1, max_length=128, description="可选：临时覆盖路由模型")

    model_config = ConfigDict(extra="forbid")


class ProjectMemoryRouteDryRunResponse(BaseModel):
    project_id: UUID
    router_logical_model: str
    should_store: bool
    scope: MemoryScope
    memory_text: str
    memory_items: list[MemoryItem]
    structured_ops: list[StructuredOp] = Field(default_factory=list, description="可选：结构化属性操作（用于确定性存储）")
    raw_model_output: str


__all__ = [
    "MemoryItem",
    "MemoryScope",
    "StructuredOp",
    "ProjectMemoryRouteDryRunRequest",
    "ProjectMemoryRouteDryRunResponse",
]
