from enum import Enum
from typing import Any, Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, ConfigDict, model_validator

from app.provider.sdk_selector import list_registered_sdk_vendors

SdkVendorValue = str


class ProviderStatus(str, Enum):
    """
    Runtime health state for a provider.
    Mirrors the enum defined in specs/001-model-routing/data-model.md.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ProviderAPIKey(BaseModel):
    """
    A single API key entry for a provider, with optional weight and limits.
    """

    key: str = Field(..., description="API authentication key or token")
    weight: float = Field(
        default=1.0,
        description="Relative routing weight when the provider has multiple keys",
        gt=0,
    )
    max_qps: int | None = Field(
        default=None,
        description="Optional per-key QPS limit; when reached this key is temporarily skipped",
        gt=0,
    )
    label: str | None = Field(
        default=None,
        description="Optional label for observability; key material is never logged",
    )


class ProviderConfig(BaseModel):
    """
    Static configuration for a model provider, usually loaded from env.
    """

    id: str = Field(..., description="Provider unique identifier (short slug)")
    name: str = Field(..., description="Human readable provider name")
    base_url: HttpUrl = Field(..., description="API base URL")
    api_key: str | None = Field(
        None, description="API authentication key or token (legacy single-key field)"
    )
    api_keys: list[ProviderAPIKey] | None = Field(
        default=None,
        description="Weighted pool of API keys for this provider",
    )
    models_path: str = Field(
        default="/v1/models", description="Path for listing models"
    )
    messages_path: str | None = Field(
        default="/v1/message",
        description=(
            "Preferred Claude Messages API path. Set to empty/None when the "
            "provider only supports chat completions and requires fallback."
        ),
    )
    chat_completions_path: str = Field(
        default="/v1/chat/completions",
        description="Preferred Chat Completions endpoint path",
    )
    responses_path: str | None = Field(
        default=None,
        description="Optional Responses API endpoint path",
    )
    weight: float = Field(
        default=1.0,
        description="Base routing weight used by the scheduler",
        gt=0,
    )
    region: str | None = Field(None, description="Optional region / label")
    cost_input: float | None = Field(
        None, description="Per-token input price", gt=0
    )
    cost_output: float | None = Field(
        None, description="Per-token output price", gt=0
    )
    max_qps: int | None = Field(
        None, description="Provider-level QPS limit", gt=0
    )
    custom_headers: dict[str, str] | None = Field(
        None, description="Extra headers to send to this provider"
    )
    retryable_status_codes: list[int] | None = Field(
        default=None,
        description=(
            "HTTP status codes that should be treated as retryable for this "
            "provider (e.g. [429, 500, 502, 503, 504] for OpenAI/Gemini/Claude)."
        ),
    )
    static_models: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Optional manual list of models used when the provider does not "
            "offer a /models endpoint. Each entry should match the upstream "
            "model metadata shape (at minimum include an 'id')."
        ),
    )
    transport: Literal["http", "sdk"] = Field(
        default="http",
        description="Transport type: default HTTP proxying or provider-native SDK",
    )
    provider_type: Literal["native", "aggregator"] = Field(
        default="native",
        description=(
            "Provider vendor category. Use 'native' for first-party providers and "
            "'aggregator' when routing through an intermediary platform."
        ),
    )
    sdk_vendor: SdkVendorValue | None = Field(
        default=None,
        description=(
            "When transport='sdk', identifies which official SDK implementation to use "
            "(e.g. openai/google/claude)."
        ),
    )

    supported_api_styles: list[Literal["openai", "responses", "claude"]] | None = Field(
        default=None,
        description="Explicit upstream API styles supported by this provider",
    )

    @model_validator(mode="after")
    def validate_sdk_vendor(self) -> "ProviderConfig":
        supported_vendors = list_registered_sdk_vendors()
        if self.transport == "sdk":
            if self.sdk_vendor is None:
                raise ValueError("当 transport=sdk 时，必须指定 sdk_vendor")
            if supported_vendors and self.sdk_vendor not in supported_vendors:
                raise ValueError(
                    f"sdk_vendor 不在已注册列表中: {', '.join(supported_vendors)}"
                )
        if self.transport == "http":
            self.sdk_vendor = None
        return self

    def get_api_keys(self) -> list[ProviderAPIKey]:
        """
        Return configured API keys, falling back to the legacy single-key field.
        """
        if self.api_keys:
            return list(self.api_keys)
        if self.api_key:
            return [ProviderAPIKey(key=self.api_key, label="default")]
        return []


class Provider(ProviderConfig):
    """
    Full provider information including runtime status metadata.
    """

    status: ProviderStatus = Field(
        default=ProviderStatus.HEALTHY, description="Current provider health state"
    )
    last_check: float | None = Field(
        None, description="Last health-check timestamp (epoch seconds)"
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Additional runtime metadata from health checks, etc."
    )


class ProviderAPIKeyCreateRequest(BaseModel):
    """
    创建厂商API密钥的请求模型
    """
    key: str = Field(..., description="API认证密钥或令牌")
    label: str = Field(..., description="密钥的可识别标签")
    weight: float = Field(
        default=1.0,
        description="当厂商有多个密钥时的相对路由权重",
        gt=0,
    )
    max_qps: int | None = Field(
        default=None,
        description="可选的每密钥QPS限制；达到此限制时将暂时跳过此密钥",
        gt=0,
    )
    status: str = Field(
        default="active",
        description="密钥状态：'active'或'inactive'",
    )


class ProviderAPIKeyUpdateRequest(BaseModel):
    """
    更新厂商API密钥的请求模型
    """
    key: str | None = Field(
        default=None,
        description="API认证密钥或令牌",
    )
    label: str | None = Field(
        default=None,
        description="密钥的可识别标签",
    )
    weight: float | None = Field(
        default=None,
        description="当厂商有多个密钥时的相对路由权重",
        gt=0,
    )
    max_qps: int | None = Field(
        default=None,
        description="可选的每密钥QPS限制；达到此限制时将暂时跳过此密钥",
        gt=0,
    )
    status: str | None = Field(
        default=None,
        description="密钥状态：'active'或'inactive'",
    )


class ProviderAPIKeyResponse(BaseModel):
    """
    厂商API密钥的响应模型
    """
    id: UUID
    provider_id: str
    label: str
    key_prefix: str | None = None
    weight: float
    max_qps: int | None
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProviderResponse(BaseModel):
    """
    提供商的API响应模型，用于返回提供商信息
    """
    # 直接使用 UUID / datetime 类型，方便与 ORM 模型对齐；
    # 经由 FastAPI/Pydantic 序列化后，前端仍然会收到字符串形式。
    id: UUID = Field(..., description="提供商的UUID")
    provider_id: str = Field(..., description="提供商的唯一标识符")
    name: str = Field(..., description="提供商名称")
    base_url: str = Field(..., description="API基础URL")
    transport: str = Field(default="http", description="传输类型：http或sdk")
    provider_type: str = Field(default="native", description="提供商类型：native或aggregator")
    sdk_vendor: str | None = Field(default=None, description="SDK供应商标识")
    weight: float = Field(default=1.0, description="路由权重")
    region: str | None = Field(default=None, description="区域标识")
    cost_input: float | None = Field(default=None, description="输入token价格")
    cost_output: float | None = Field(default=None, description="输出token价格")
    billing_factor: float = Field(default=1.0, description="计费因子")
    max_qps: int | None = Field(default=None, description="最大QPS限制")
    models_path: str = Field(default="/v1/models", description="模型列表路径")
    messages_path: str | None = Field(default=None, description="消息API路径")
    chat_completions_path: str = Field(default="/v1/chat/completions", description="聊天完成路径")
    responses_path: str | None = Field(default=None, description="响应API路径")
    status: str = Field(default="healthy", description="提供商状态")
    visibility: str = Field(default="public", description="可见性：public或private")
    owner_id: UUID | None = Field(default=None, description="所有者用户ID（私有提供商）")
    preset_id: str | None = Field(default=None, description="关联的预设ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "Provider",
    "ProviderAPIKey",
    "ProviderConfig",
    "ProviderStatus",
    "ProviderAPIKeyCreateRequest",
    "ProviderAPIKeyUpdateRequest",
    "ProviderAPIKeyResponse",
    "ProviderResponse",
]
