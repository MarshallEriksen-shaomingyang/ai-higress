from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


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
    id: str
    provider_id: str
    label: str
    weight: float
    max_qps: int | None
    status: str
    created_at: str
    updated_at: str | None = None
    
    class Config:
        from_attributes = True


__all__ = [
    "Provider", 
    "ProviderAPIKey", 
    "ProviderConfig", 
    "ProviderStatus",
    "ProviderAPIKeyCreateRequest",
    "ProviderAPIKeyUpdateRequest",
    "ProviderAPIKeyResponse",
]
