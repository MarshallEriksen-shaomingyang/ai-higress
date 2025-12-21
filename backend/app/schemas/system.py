from enum import Enum

from pydantic import BaseModel, Field


class SecretKeyGenerationRequest(BaseModel):
    length: int = Field(default=64, ge=32, le=256, description="密钥长度")


class SecretKeyResponse(BaseModel):
    secret_key: str = Field(..., description="生成的系统密钥")


class SystemAdminInitRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="管理员用户名")
    email: str = Field(..., description="管理员邮箱")
    display_name: str = Field(default="System Administrator", description="管理员显示名称")


class SystemAdminInitResponse(BaseModel):
    username: str
    email: str
    password: str


class KeyValidationRequest(BaseModel):
    key: str = Field(..., description="要验证的密钥")


class KeyValidationResponse(BaseModel):
    is_valid: bool = Field(..., description="密钥是否有效")
    message: str = Field(..., description="验证结果消息")


class ProviderLimitsResponse(BaseModel):
    """系统级提供商限制配置。"""

    default_user_private_provider_limit: int
    max_user_private_provider_limit: int
    require_approval_for_shared_providers: bool


class ProviderLimitsUpdateRequest(BaseModel):
    default_user_private_provider_limit: int = Field(ge=0)
    max_user_private_provider_limit: int = Field(ge=0)
    require_approval_for_shared_providers: bool


class GatewayConfig(BaseModel):
    """对外暴露给用户查看的网关基础配置信息。"""

    api_base_url: str = Field(..., description="网关 API 的基础 URL，例如 https://api.example.com")
    max_concurrent_requests: int = Field(
        ...,
        ge=1,
        description="推荐/配置的最大并发请求数",
    )
    request_timeout_ms: int = Field(
        ...,
        ge=1,
        description="推荐给调用方的单次请求超时时间（毫秒）",
    )
    cache_ttl_seconds: int = Field(
        ...,
        ge=0,
        description="推荐的缓存 TTL（秒）",
    )
    probe_prompt: str | None = Field(
        default=None,
        description="预留字段：将来用于 health 全局扩展的探针提示词（当前版本不生效）",
    )
    metrics_retention_days: int = Field(
        default=15,
        ge=7,
        le=30,
        description="指标历史保留天数（分钟桶；用于控制 provider_routing_metrics_history 的留存）",
    )


class GatewayConfigUpdateRequest(GatewayConfig):
    """更新网关配置时使用的请求体。当前与响应字段一致。"""


class CacheSegment(str, Enum):
    """可清理的缓存分组枚举。"""

    MODELS = "models"
    METRICS_OVERVIEW = "metrics_overview"
    USER_METRICS_OVERVIEW = "user_metrics_overview"
    PROVIDER_MODELS = "provider_models"
    LOGICAL_MODELS = "logical_models"
    ROUTING_METRICS = "routing_metrics"


class CacheClearRequest(BaseModel):
    """
    清理缓存的请求体。

    - segments 为空列表时，后端可以选择默认清理所有分组；
      当前实现为：空列表则表示“全部分组”。
    """

    segments: list[CacheSegment] = Field(
        default_factory=list,
        description="要清理的缓存分组列表，为空时表示全部分组",
    )


class CacheClearResponse(BaseModel):
    """清理缓存操作的结果。"""

    cleared_keys: int = Field(..., description="被删除的缓存键总数")
    patterns: dict[str, int] = Field(
        ...,
        description="按模式统计删除数量，例如 {'gateway:models:all': 1, 'metrics:overview:*': 3}",
    )


__all__ = [
    "CacheClearRequest",
    "CacheClearResponse",
    "CacheSegment",
    "GatewayConfig",
    "GatewayConfigUpdateRequest",
    "KeyValidationRequest",
    "KeyValidationResponse",
    "ProviderLimitsResponse",
    "ProviderLimitsUpdateRequest",
    "SecretKeyGenerationRequest",
    "SecretKeyResponse",
    "SystemAdminInitRequest",
    "SystemAdminInitResponse",
]
