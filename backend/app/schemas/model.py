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


__all__ = ["Model", "ModelCapability"]

