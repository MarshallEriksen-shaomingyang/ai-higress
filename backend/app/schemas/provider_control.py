from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class UserProviderCreateRequest(BaseModel):
    """创建用户私有提供商的请求模型。"""

    provider_id: str = Field(..., min_length=1, max_length=50, description="用于路由及授权的唯一短 ID")
    name: str = Field(..., min_length=1, max_length=100, description="展示用名称")
    base_url: HttpUrl = Field(..., description="上游 API 的 base URL")
    api_key: str = Field(..., min_length=1, description="上游厂商 API Key，将以加密形式存储")

    provider_type: Literal["native", "aggregator"] = Field(
        default="native",
        description="提供商类型，native=直连厂商，aggregator=聚合平台",
    )
    transport: Literal["http", "sdk"] = Field(
        default="http",
        description="调用方式：HTTP 代理或 SDK",
    )
    weight: float | None = Field(
        default=1.0,
        description="用于路由的基础权重",
        gt=0,
    )
    region: str | None = Field(default=None, description="可选区域标签")
    cost_input: float | None = Field(default=None, gt=0)
    cost_output: float | None = Field(default=None, gt=0)
    max_qps: int | None = Field(default=None, gt=0)
    retryable_status_codes: List[int] | None = Field(default=None)
    custom_headers: Dict[str, str] | None = Field(default=None)
    models_path: str | None = Field(default="/v1/models")
    messages_path: str | None = Field(default="/v1/message")
    static_models: List[Dict[str, Any]] | None = Field(
        default=None,
        description="当上游不提供 /models 时可手动配置的模型列表",
    )


class UserProviderUpdateRequest(BaseModel):
    """更新用户私有提供商的请求模型。"""

    name: str | None = Field(default=None, max_length=100)
    base_url: HttpUrl | None = None
    provider_type: Literal["native", "aggregator"] | None = None
    transport: Literal["http", "sdk"] | None = None
    weight: float | None = Field(default=None, gt=0)
    region: str | None = None
    cost_input: float | None = Field(default=None, gt=0)
    cost_output: float | None = Field(default=None, gt=0)
    max_qps: int | None = Field(default=None, gt=0)
    retryable_status_codes: List[int] | None = None
    custom_headers: Dict[str, str] | None = None
    models_path: str | None = None
    messages_path: str | None = None
    static_models: List[Dict[str, Any]] | None = None

    @model_validator(mode="after")
    def ensure_any_field(self) -> "UserProviderUpdateRequest":
        if all(
            getattr(self, field) is None
            for field in (
                "name",
                "base_url",
                "provider_type",
                "transport",
                "weight",
                "region",
                "cost_input",
                "cost_output",
                "max_qps",
                "retryable_status_codes",
                "custom_headers",
                "models_path",
                "messages_path",
                "static_models",
            )
        ):
            raise ValueError("至少需要提供一个可更新字段")
        return self


class UserProviderResponse(BaseModel):
    """用户私有提供商的响应模型。"""

    id: UUID
    provider_id: str
    name: str
    base_url: HttpUrl
    provider_type: str
    transport: str
    visibility: str
    owner_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderSubmissionRequest(BaseModel):
    """用户提交共享池提供商的请求模型。"""

    name: str = Field(..., max_length=100)
    provider_id: str = Field(..., max_length=50)
    base_url: HttpUrl
    provider_type: Literal["native", "aggregator"] = "native"
    api_key: str = Field(..., min_length=1, description="上游厂商 API Key")
    description: str | None = Field(default=None, max_length=2000)
    extra_config: Dict[str, Any] | None = Field(
        default=None,
        description="可选的扩展配置，例如自定义 header、模型路径等",
    )


class ProviderSubmissionResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    provider_id: str
    base_url: HttpUrl
    provider_type: str
    description: str | None
    approval_status: str
    reviewed_by: UUID | None
    review_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderReviewRequest(BaseModel):
    """管理员审核共享提供商的请求模型。"""

    approved: bool = Field(..., description="是否通过该提交")
    review_notes: str | None = Field(default=None, max_length=2000)


class ProviderValidationResult(BaseModel):
    """提供商配置验证结果。"""

    is_valid: bool
    error_message: str | None = None
    metadata: Dict[str, Any] | None = None


class UserPermissionResponse(BaseModel):
    id: UUID
    user_id: UUID
    permission_type: str
    permission_value: str | None
    expires_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPermissionGrantRequest(BaseModel):
    permission_type: str = Field(..., max_length=32)
    permission_value: str | None = Field(default=None, max_length=100)
    expires_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AdminProviderResponse(BaseModel):
    """管理员视角的 Provider 信息。"""

    id: UUID
    provider_id: str
    name: str
    base_url: HttpUrl
    provider_type: str
    transport: str
    visibility: str
    owner_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminProvidersResponse(BaseModel):
    providers: List[AdminProviderResponse]
    total: int


class ProviderVisibilityUpdateRequest(BaseModel):
    visibility: Literal["public", "restricted", "private"]


__all__ = [
    "AdminProviderResponse",
    "AdminProvidersResponse",
    "ProviderReviewRequest",
    "ProviderSubmissionRequest",
    "ProviderSubmissionResponse",
    "ProviderValidationResult",
    "ProviderVisibilityUpdateRequest",
    "UserPermissionGrantRequest",
    "UserPermissionResponse",
    "UserProviderCreateRequest",
    "UserProviderUpdateRequest",
    "UserProviderResponse",
]

