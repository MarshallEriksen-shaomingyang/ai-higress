from typing import Any

from pydantic import BaseModel, Field

from .provider import ProviderConfig, SdkVendorValue
from .routing_metrics import RoutingMetrics


class ProvidersResponse(BaseModel):
    providers: list[ProviderConfig] = Field(default_factory=list)
    total: int


class ProviderModelsResponse(BaseModel):
    models: list[dict[str, Any]] = Field(default_factory=list)
    total: int


class ProviderMetricsResponse(BaseModel):
    metrics: list[RoutingMetrics] = Field(default_factory=list)


class SDKVendorsResponse(BaseModel):
    vendors: list[SdkVendorValue] = Field(default_factory=list)
    total: int


__all__ = [
    "ProviderMetricsResponse",
    "ProviderModelsResponse",
    "ProvidersResponse",
    "SDKVendorsResponse",
]
