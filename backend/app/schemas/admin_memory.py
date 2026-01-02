from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.memory_route import MemoryScope


class AdminMemoryItemResponse(BaseModel):
    id: str = Field(..., description="记忆单元 ID (Qdrant point_id)")
    content: str = Field(..., description="记忆内容")
    categories: Optional[List[str]] = Field(default=None, description="分类")
    keywords: Optional[List[str]] = Field(default=None, description="关键词")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    scope: MemoryScope = Field(..., description="作用域")
    approved: bool = Field(..., description="是否已审核通过")
    submitted_by_user_id: Optional[UUID] = Field(default=None, description="提交者 ID (如果是 AI 自动挖掘，则为来源用户)")
    source_id: Optional[str] = Field(default=None, description="来源会话 ID")


class AdminMemoryApproveRequest(BaseModel):
    project_id: UUID = Field(..., description="用于路由/配额/审计的项目 ID（即 API Key ID）")
    content: Optional[str] = Field(default=None, min_length=1, description="可选：修正后的内容")
    categories: Optional[List[str]] = Field(default=None, description="可选：修正后的分类")
    keywords: Optional[List[str]] = Field(default=None, description="可选：修正后的关键词")


class AdminMemoryCreateRequest(BaseModel):
    project_id: UUID = Field(..., description="用于路由/配额/审计的项目 ID（即 API Key ID）")
    content: str = Field(..., min_length=1, description="记忆内容")
    categories: List[str] = Field(default_factory=list, description="分类")
    keywords: List[str] = Field(default_factory=list, description="关键词")


class AdminMemoryListResponse(BaseModel):
    items: List[AdminMemoryItemResponse] = Field(default_factory=list)
    next_offset: Optional[str] = Field(default=None, description="下一页游标")
    total: Optional[int] = Field(default=None, description="总数（估算）")
