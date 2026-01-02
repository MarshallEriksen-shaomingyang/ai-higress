from __future__ import annotations

from pydantic import BaseModel, Field


class AdminSystemConfigUpsertRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=255, description="配置 Key（建议使用 env 变量名作为 Key）")
    value: str | None = Field(default=None, description="配置值；传 null 表示清空 DB 覆盖并回退到 env")
    description: str | None = Field(default=None, max_length=512, description="可选：配置说明（仅用于管理端展示）")


class AdminSystemConfigResponse(BaseModel):
    key: str
    value: str | None
    source: str = Field(..., description="值来源：db/env")


__all__ = [
    "AdminSystemConfigResponse",
    "AdminSystemConfigUpsertRequest",
]

