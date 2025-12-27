from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelCapability(str, Enum):
    """
    Capability flags for a model, e.g. chat vs embedding.
    """

    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"
    AUDIO = "audio"
    FUNCTION_CALLING = "function_calling"
    IMAGE_GENERATION = "image_generation"


class Model(BaseModel):
    """
    Normalised model information for a single provider.
    """

    model_id: str = Field(..., description="Model identifier on the provider side")
    provider_id: str = Field(..., description="Owning provider id")
    family: str = Field(..., description="Model family name")
    display_name: str = Field(..., description="Human readable display name")
    context_length: int = Field(
        ..., description="Maximum context length in tokens", gt=0
    )
    capabilities: list[ModelCapability] = Field(
        ..., description="List of supported capabilities"
    )
    pricing: dict[str, float] | None = Field(
        None, description="Optional pricing information"
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Original upstream metadata payload"
    )
    meta_hash: str | None = Field(
        None, description="Hash of model metadata for change detection"
    )


class ModelPricingUpdateRequest(BaseModel):
    """
    管理端更新单个物理模型计费配置的请求体。

    约定：
    - 单位为「每 1000 tokens 消耗的积分数」；
    - 只填充的字段会被更新，未提供的字段保持不变；
    - 若两个字段均为 None，则会清空现有 pricing。
    """

    input: float | None = Field(
        default=None, ge=0, description="每 1000 输入 tokens 消耗的积分数"
    )
    output: float | None = Field(
        default=None, ge=0, description="每 1000 输出 tokens 消耗的积分数"
    )


class ProviderModelPricingResponse(BaseModel):
    """
    返回 provider+model 维度的计费配置。
    """

    provider_id: str = Field(..., description="Provider 的短 ID（例如 moonshot-xxx）")
    model_id: str = Field(..., description="上游模型 ID")
    pricing: dict[str, float] | None = Field(
        default=None,
        description="当前计费配置（单位：每 1000 tokens 的积分数，例如 {'input': 5, 'output': 15}）",
    )


class ModelAliasUpdateRequest(BaseModel):
    """
    更新单个物理模型「别名映射」的请求体。

    - alias 为 None 或空字符串时，表示清除当前映射；
    - alias 为非空字符串时，将该值作为此物理模型的对外别名。
    """

    alias: str | None = Field(
        default=None,
        description="要为该物理模型设置的别名，如 'claude-sonnet-4-5'",
    )


class ProviderModelAliasResponse(BaseModel):
    """
    返回 provider+model 维度的别名映射配置。
    """

    provider_id: str = Field(..., description="Provider 的短 ID（例如 moonshot-xxx）")
    model_id: str = Field(..., description="上游模型 ID")
    alias: str | None = Field(
        default=None,
        description="当前配置的模型别名（例如 'claude-sonnet-4-5'），为空表示未配置映射",
    )


class ModelCapabilitiesUpdateRequest(BaseModel):
    """
    更新单个物理模型「能力列表」的请求体。

    - capabilities 为该物理模型的能力枚举列表；
    - 该配置会覆盖上游 /models 返回的能力，用于处理上游未正确声明能力的情况。
    """

    capabilities: list[ModelCapability] = Field(
        ...,
        min_length=1,
        description="要为该物理模型设置的能力列表",
    )


class ProviderModelCapabilitiesResponse(BaseModel):
    """
    返回 provider+model 维度的能力配置。
    """

    provider_id: str = Field(..., description="Provider 的短 ID（例如 moonshot-xxx）")
    model_id: str = Field(..., description="上游模型 ID")
    capabilities: list[ModelCapability] = Field(
        default_factory=list,
        description="当前配置的能力列表",
    )


class ModelDisableUpdateRequest(BaseModel):
    """
    更新单个物理模型「禁用状态」的请求体。

    - disabled=true：禁用该 Provider 下的该模型（不参与 /models 聚合与路由）。
    - disabled=false：恢复启用。
    """

    disabled: bool = Field(
        ...,
        description="是否禁用该 Provider 下的该模型",
    )


class ProviderModelDisabledResponse(BaseModel):
    """
    返回 provider+model 维度的禁用状态。
    """

    provider_id: str = Field(..., description="Provider 的短 ID（例如 moonshot-xxx）")
    model_id: str = Field(..., description="上游模型 ID")
    disabled: bool = Field(..., description="当前是否已禁用该模型")


__all__ = [
    "Model",
    "ModelAliasUpdateRequest",
    "ModelCapability",
    "ModelCapabilitiesUpdateRequest",
    "ModelDisableUpdateRequest",
    "ModelPricingUpdateRequest",
    "ProviderModelAliasResponse",
    "ProviderModelCapabilitiesResponse",
    "ProviderModelDisabledResponse",
    "ProviderModelPricingResponse",
]
