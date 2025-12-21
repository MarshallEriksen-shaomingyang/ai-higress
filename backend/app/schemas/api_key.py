from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class APIKeyExpiry(str, Enum):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    NEVER = "never"


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    expiry: APIKeyExpiry = Field(
        default=APIKeyExpiry.NEVER, description="密钥有效期（周、月、年、不过期）"
    )
    allowed_provider_ids: list[str] | None = Field(
        default=None,
        description="允许访问的 provider_id 列表；省略表示无限制",
    )


class APIKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    expiry: APIKeyExpiry | None = Field(
        default=None, description="新的有效期选项；留空表示保持不变"
    )
    allowed_provider_ids: list[str] | None = Field(
        default=None,
        description="新的 provider_id 列表；空数组表示清除限制",
    )

    @model_validator(mode="after")
    def ensure_any_field(self) -> APIKeyUpdateRequest:
        if (
            self.name is None
            and self.expiry is None
            and self.allowed_provider_ids is None
        ):
            raise ValueError("至少需要提供一个可更新字段")
        return self


class APIKeyResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    key_prefix: str
    expiry_type: APIKeyExpiry
    expires_at: datetime | None = None
    is_active: bool
    disabled_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    has_provider_restrictions: bool
    allowed_provider_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class APIKeyCreateResponse(APIKeyResponse):
    token: str = Field(
        ...,
        description="系统生成的完整密钥，仅在创建时返回，请立即保存",
    )


class APIKeyAllowedProvidersRequest(BaseModel):
    allowed_provider_ids: list[str] = Field(
        default_factory=list,
        description="新的 provider_id 列表；为空表示清除限制",
    )


class APIKeyAllowedProvidersResponse(BaseModel):
    has_provider_restrictions: bool
    allowed_provider_ids: list[str] = Field(default_factory=list)




__all__ = [
    "APIKeyAllowedProvidersRequest",
    "APIKeyAllowedProvidersResponse",
    "APIKeyCreateRequest",
    "APIKeyCreateResponse",
    "APIKeyExpiry",
    "APIKeyResponse",
    "APIKeyUpdateRequest",
]
