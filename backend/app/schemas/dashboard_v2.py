from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class DashboardTimeRange(str):
    TODAY = "today"
    LAST_7D = "7d"
    LAST_30D = "30d"


class DashboardTokens(BaseModel):
    input: int = Field(0, description="输入 Token 总量（可能为 0，表示缺少拆分数据）")
    output: int = Field(0, description="输出 Token 总量（可能为 0，表示缺少拆分数据）")
    total: int = Field(0, description="总 Token")
    estimated_requests: int = Field(0, description="估算 Token 的请求数（用于解释口径）")


class UserDashboardKpis(BaseModel):
    time_range: str
    total_requests: int
    error_rate: float
    latency_p95_ms: float
    tokens: DashboardTokens
    credits_spent: int = Field(0, description="该时间范围内消耗的积分（credits）")


class SystemDashboardKpis(BaseModel):
    time_range: str
    total_requests: int
    error_rate: float
    latency_p95_ms: float
    tokens: DashboardTokens


class DashboardPulsePoint(BaseModel):
    window_start: dt.datetime
    total_requests: int
    error_4xx_requests: int = 0
    error_5xx_requests: int = 0
    error_429_requests: int = 0
    error_timeout_requests: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0


class DashboardPulse(BaseModel):
    points: list[DashboardPulsePoint] = Field(default_factory=list)


class DashboardTokenPoint(BaseModel):
    window_start: dt.datetime
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_requests: int = 0


class DashboardTokensTimeSeries(BaseModel):
    time_range: str
    bucket: str
    points: list[DashboardTokenPoint] = Field(default_factory=list)


class DashboardTopModel(BaseModel):
    model: str
    requests: int
    tokens_total: int = 0


class DashboardTopModels(BaseModel):
    items: list[DashboardTopModel] = Field(default_factory=list)


class DashboardCostByProviderItem(BaseModel):
    provider_id: str
    credits_spent: int
    transactions: int


class DashboardCostByProvider(BaseModel):
    items: list[DashboardCostByProviderItem] = Field(default_factory=list)


class DashboardProviderStatusItem(BaseModel):
    provider_id: str
    operation_status: str
    status: str
    audit_status: str
    last_check: dt.datetime | None = None


class DashboardProviderStatus(BaseModel):
    items: list[DashboardProviderStatusItem] = Field(default_factory=list)


class DashboardProviderMetricPoint(BaseModel):
    window_start: dt.datetime
    qps: float = 0.0
    error_rate: float = 0.0


class DashboardProviderMetricsItem(BaseModel):
    provider_id: str
    total_requests: int = 0
    error_rate: float = 0.0
    latency_p95_ms: float = 0.0
    qps: float = 0.0
    points: list[DashboardProviderMetricPoint] = Field(default_factory=list)


class DashboardProviderMetrics(BaseModel):
    time_range: str
    bucket: str
    items: list[DashboardProviderMetricsItem] = Field(default_factory=list)


__all__ = [
    "DashboardCostByProvider",
    "DashboardCostByProviderItem",
    "DashboardProviderMetricPoint",
    "DashboardProviderMetrics",
    "DashboardProviderMetricsItem",
    "DashboardProviderStatus",
    "DashboardProviderStatusItem",
    "DashboardPulse",
    "DashboardPulsePoint",
    "DashboardTimeRange",
    "DashboardTokenPoint",
    "DashboardTokens",
    "DashboardTokensTimeSeries",
    "DashboardTopModel",
    "DashboardTopModels",
    "SystemDashboardKpis",
    "UserDashboardKpis",
]
