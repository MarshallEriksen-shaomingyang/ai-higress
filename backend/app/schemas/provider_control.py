from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.provider.sdk_selector import list_registered_sdk_vendors
from app.schemas.provider import SdkVendorValue

ApiStyleValue = Literal["openai", "responses", "claude"]


def _validate_sdk_vendor_value(value: str | None) -> str | None:
    if value is None:
        return None
    supported = list_registered_sdk_vendors()
    if supported and value not in supported:
        raise ValueError(f"sdk_vendor 不在已注册列表中: {', '.join(supported)}")
    return value


class UserProviderCreateRequest(BaseModel):
    """创建用户私有提供商的请求模型。"""

    preset_id: str | None = Field(default=None, description="可选的官方预设 ID")
    name: str | None = Field(default=None, min_length=1, max_length=100, description="展示用名称")
    base_url: HttpUrl | None = Field(default=None, description="上游 API 的 base URL")
    api_key: str = Field(..., min_length=1, description="上游厂商 API Key，将以加密形式存储")

    provider_type: Literal["native", "aggregator"] = Field(
        default="native",
        description="提供商类型，native=直连厂商，aggregator=聚合平台",
    )
    transport: Literal["http", "sdk"] = Field(
        default="http",
        description="调用方式：HTTP 代理或 SDK",
    )
    sdk_vendor: SdkVendorValue | None = Field(
        default=None,
        description="当 transport=sdk 时必须指定的 SDK 厂商标识，例如 openai/google/claude",
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
    chat_completions_path: str | None = Field(default="/v1/chat/completions")
    responses_path: str | None = Field(default=None)
    supported_api_styles: List[ApiStyleValue] | None = Field(default=None)
    static_models: List[Dict[str, Any]] | None = Field(
        default=None,
        description="当上游不提供 /models 时可手动配置的模型列表",
    )

    @model_validator(mode="after")
    def ensure_required_fields(self) -> "UserProviderCreateRequest":
        if self.preset_id:
            return self
        required = {
            "name": self.name,
            "base_url": self.base_url,
        }
        missing = [field for field, value in required.items() if value in (None, "")]
        if missing:
            raise ValueError("当未指定 preset_id 时，name/base_url 均为必填")
        return self

    @model_validator(mode="after")
    def validate_paths(self) -> "UserProviderCreateRequest":
        for field_name in (
            "models_path",
            "messages_path",
            "chat_completions_path",
            "responses_path",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            trimmed = value.strip()
            if not trimmed:
                setattr(self, field_name, None)
                continue
            if not trimmed.startswith("/"):
                raise ValueError(f"{field_name} 必须以 / 开头")
            setattr(self, field_name, trimmed)
        return self

    @model_validator(mode="after")
    def validate_sdk_vendor(self) -> "UserProviderCreateRequest":
        # 明确约束：仅当 transport=sdk 时才需要 sdk_vendor
        if self.transport == "sdk":
            if self.sdk_vendor is None:
                raise ValueError("当 transport=sdk 时，必须指定 sdk_vendor")
            self.sdk_vendor = _validate_sdk_vendor_value(self.sdk_vendor)
        if self.transport == "http":
            # HTTP 模式下忽略 sdk_vendor，避免产生误导
            self.sdk_vendor = None
        return self


class UserQuotaResponse(BaseModel):
    """用户私有 Provider 配额信息。"""

    private_provider_limit: int = Field(
        ...,
        ge=0,
        description="当前用户可创建的私有 Provider 数量上限（用于展示）；对无限制用户为推荐展示值。",
    )
    private_provider_count: int = Field(
        ...,
        ge=0,
        description="当前用户已创建的私有 Provider 数量。",
    )
    is_unlimited: bool = Field(
        ...,
        description="是否在后端层面对用户的私有 Provider 数量不做硬性限制。",
    )


class UserProviderUpdateRequest(BaseModel):
    """更新用户私有提供商的请求模型。"""

    name: str | None = Field(default=None, max_length=100)
    base_url: HttpUrl | None = None
    provider_type: Literal["native", "aggregator"] | None = None
    transport: Literal["http", "sdk"] | None = None
    sdk_vendor: SdkVendorValue | None = None
    weight: float | None = Field(default=None, gt=0)
    region: str | None = None
    cost_input: float | None = Field(default=None, gt=0)
    cost_output: float | None = Field(default=None, gt=0)
    max_qps: int | None = Field(default=None, gt=0)
    retryable_status_codes: List[int] | None = None
    custom_headers: Dict[str, str] | None = None
    models_path: str | None = None
    messages_path: str | None = None
    chat_completions_path: str | None = None
    responses_path: str | None = None
    supported_api_styles: List[ApiStyleValue] | None = None
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
                "sdk_vendor",
                "weight",
                "region",
                "cost_input",
                "cost_output",
                "max_qps",
                "retryable_status_codes",
                "custom_headers",
                "models_path",
                "messages_path",
                "chat_completions_path",
                "responses_path",
                "supported_api_styles",
                "static_models",
            )
        ):
            raise ValueError("至少需要提供一个可更新字段")
        return self

    @model_validator(mode="after")
    def normalize_paths(self) -> "UserProviderUpdateRequest":
        for field_name in (
            "models_path",
            "messages_path",
            "chat_completions_path",
            "responses_path",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            trimmed = value.strip()
            if not trimmed.startswith("/"):
                raise ValueError(f"{field_name} 必须以 / 开头")
            setattr(self, field_name, trimmed)
        return self

    @model_validator(mode="after")
    def validate_sdk_vendor(self) -> "UserProviderUpdateRequest":
        if self.sdk_vendor is not None:
            self.sdk_vendor = _validate_sdk_vendor_value(self.sdk_vendor)
        # 如果显式切换到 HTTP，则清空 sdk_vendor
        if self.transport == "http":
            self.sdk_vendor = None
        return self


class UserProviderResponse(BaseModel):
    """用户私有提供商的响应模型。"""

    id: UUID
    provider_id: str
    name: str
    base_url: HttpUrl
    provider_type: str
    transport: str
    sdk_vendor: str | None = None
    preset_id: str | None = None
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
    sdk_vendor: str | None = None
    preset_id: str | None = None
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


class ProviderPresetBase(BaseModel):
    preset_id: str = Field(..., min_length=1, max_length=50, description="官方预设 ID")
    display_name: str = Field(..., max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    provider_type: Literal["native", "aggregator"] = Field(default="native")
    transport: Literal["http", "sdk"] = Field(default="http")
    sdk_vendor: SdkVendorValue | None = Field(
        default=None,
        description="当 transport=sdk 时必须指定的 SDK 厂商标识，例如 openai/google/claude",
    )
    base_url: HttpUrl
    models_path: str = Field(default="/v1/models")
    messages_path: str | None = Field(default="/v1/message")
    chat_completions_path: str = Field(default="/v1/chat/completions")
    responses_path: str | None = Field(default=None)
    supported_api_styles: List[ApiStyleValue] | None = Field(default=None)
    retryable_status_codes: List[int] | None = Field(default=None)
    custom_headers: Dict[str, str] | None = Field(default=None)
    static_models: List[Dict[str, Any]] | None = Field(default=None)

    @model_validator(mode="after")
    def ensure_paths(self) -> "ProviderPresetBase":
        for field_name in (
            "models_path",
            "messages_path",
            "chat_completions_path",
            "responses_path",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            trimmed = value.strip()
            if not trimmed:
                setattr(self, field_name, None)
                continue
            if not trimmed.startswith("/"):
                raise ValueError(f"{field_name} 必须以 / 开头")
            setattr(self, field_name, trimmed)
        return self

    @model_validator(mode="after")
    def validate_sdk_vendor(self) -> "ProviderPresetBase":
        if self.transport == "sdk":
            if self.sdk_vendor is None:
                raise ValueError("当 transport=sdk 时，必须指定 sdk_vendor")
            self.sdk_vendor = _validate_sdk_vendor_value(self.sdk_vendor)
        if self.transport == "http":
            self.sdk_vendor = None
        return self

    model_config = ConfigDict(from_attributes=True)


class ProviderPresetCreateRequest(ProviderPresetBase):
    pass


class ProviderPresetUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    provider_type: Literal["native", "aggregator"] | None = None
    transport: Literal["http", "sdk"] | None = None
    sdk_vendor: SdkVendorValue | None = None
    base_url: HttpUrl | None = None
    models_path: str | None = None
    messages_path: str | None = None
    chat_completions_path: str | None = None
    responses_path: str | None = None
    supported_api_styles: List[ApiStyleValue] | None = None
    retryable_status_codes: List[int] | None = None
    custom_headers: Dict[str, str] | None = None
    static_models: List[Dict[str, Any]] | None = None

    @model_validator(mode="after")
    def ensure_any_field(self) -> "ProviderPresetUpdateRequest":
        if all(
            getattr(self, attr) is None
            for attr in (
                "display_name",
                "description",
                "provider_type",
                "transport",
                "sdk_vendor",
                "base_url",
                "models_path",
                "messages_path",
                "chat_completions_path",
                "responses_path",
                "supported_api_styles",
                "retryable_status_codes",
                "custom_headers",
                "static_models",
            )
        ):
            raise ValueError("至少需要提供一个可更新字段")
        return self

    @model_validator(mode="after")
    def normalize_paths(self) -> "ProviderPresetUpdateRequest":
        for field_name in (
            "models_path",
            "messages_path",
            "chat_completions_path",
            "responses_path",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            trimmed = value.strip()
            if not trimmed.startswith("/"):
                raise ValueError(f"{field_name} 必须以 / 开头")
            setattr(self, field_name, trimmed)
        return self

    @model_validator(mode="after")
    def validate_sdk_vendor(self) -> "ProviderPresetUpdateRequest":
        if self.sdk_vendor is not None:
            self.sdk_vendor = _validate_sdk_vendor_value(self.sdk_vendor)
        if self.transport == "http":
            self.sdk_vendor = None
        return self


class ProviderPresetResponse(ProviderPresetBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderPresetListResponse(BaseModel):
    items: List[ProviderPresetResponse]
    total: int


class ProviderPresetImportError(BaseModel):
    preset_id: str
    reason: str


class ProviderPresetImportResult(BaseModel):
    created: List[str] = Field(default_factory=list, description="成功创建的预设ID列表")
    updated: List[str] = Field(default_factory=list, description="成功覆盖更新的预设ID列表")
    skipped: List[str] = Field(default_factory=list, description="因已存在且未开启覆盖而跳过的预设ID列表")
    failed: List[ProviderPresetImportError] = Field(default_factory=list, description="导入失败的预设及原因")


class ProviderPresetImportRequest(BaseModel):
    presets: List[ProviderPresetBase] = Field(default_factory=list, min_length=1, description="要导入的预设列表")
    overwrite: bool = Field(
        default=False,
        description="是否覆盖已存在的同名预设；默认不覆盖，若为false则同名预设会被跳过",
    )


class ProviderPresetExportResponse(BaseModel):
    presets: List[ProviderPresetBase]
    total: int


class PermissionResponse(BaseModel):
    """权限定义信息。"""

    id: UUID
    code: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleResponse(BaseModel):
    """角色基础信息。"""

    id: UUID
    code: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    code: str = Field(..., max_length=64, description="角色唯一编码")
    name: str = Field(..., max_length=100, description="角色名称")
    description: str | None = Field(
        default=None, max_length=2000, description="角色描述"
    )


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def ensure_any_field(self) -> "RoleUpdateRequest":
        if self.name is None and self.description is None:
            raise ValueError("至少需要提供一个可更新字段")
        return self


class RolePermissionsResponse(BaseModel):
    role_id: UUID
    role_code: str
    permission_codes: List[str]


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: List[str] = Field(
        default_factory=list,
        description="要设置到该角色上的权限 code 列表（全量覆盖）",
    )


class UserRolesUpdateRequest(BaseModel):
    role_ids: List[UUID] = Field(
        default_factory=list,
        description="要设置给用户的角色 ID 列表（全量覆盖）",
    )


__all__ = [
    "AdminProviderResponse",
    "AdminProvidersResponse",
    "ProviderPresetBase",
    "ProviderPresetCreateRequest",
    "ProviderPresetUpdateRequest",
    "ProviderPresetResponse",
    "ProviderPresetListResponse",
    "ProviderPresetImportRequest",
    "ProviderPresetImportResult",
    "ProviderPresetImportError",
    "ProviderPresetExportResponse",
    "ProviderReviewRequest",
    "ProviderSubmissionRequest",
    "ProviderSubmissionResponse",
    "ProviderValidationResult",
    "ProviderVisibilityUpdateRequest",
    "PermissionResponse",
    "RoleCreateRequest",
    "RolePermissionsResponse",
    "RolePermissionsUpdateRequest",
    "RoleResponse",
    "UserRolesUpdateRequest",
    "UserPermissionGrantRequest",
    "UserPermissionResponse",
    "UserProviderCreateRequest",
    "UserProviderUpdateRequest",
    "UserProviderResponse",
    "UserQuotaResponse",
]
