from pydantic import BaseModel, Field

from .provider import ProviderStatus


class RoutingMetrics(BaseModel):
    """
    Aggregated routing metrics per (logical_model, provider).
    """

    logical_model: str = Field(..., description="Logical model id")
    provider_id: str = Field(..., description="Provider id")
    latency_p95_ms: float = Field(..., description="P95 latency in milliseconds", gt=0)
    latency_p99_ms: float = Field(..., description="P99 latency in milliseconds", gt=0)
    error_rate: float = Field(
        ..., description="Error rate in [0, 1]", ge=0.0, le=1.0
    )
    success_qps_1m: float = Field(
        ..., description="Successful QPS in last minute", ge=0.0
    )
    total_requests_1m: int = Field(
        ..., description="Total requests in last minute", ge=0
    )
    last_updated: float = Field(..., description="Last update timestamp (epoch seconds)")
    status: ProviderStatus = Field(
        ..., description="Provider status derived from metrics window"
    )


class MetricsHistory(BaseModel):
    """
    Raw time-series metrics sample, used for trend analysis.
    """

    provider_id: str = Field(..., description="Provider id")
    logical_model: str = Field(..., description="Logical model id")
    timestamp: float = Field(..., description="Sample timestamp (epoch seconds)")
    latency_ms: float = Field(..., description="Observed latency in ms", gt=0)
    success: bool = Field(..., description="Whether the call succeeded")


__all__ = ["MetricsHistory", "RoutingMetrics"]

