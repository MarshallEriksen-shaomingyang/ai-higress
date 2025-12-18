from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class MetricsTimeRange(str):
    TODAY = "today"
    LAST_7D = "7d"
    LAST_30D = "30d"
    ALL = "all"


class MetricsBucket(str):
    MINUTE = "minute"


class MetricsDataPoint(BaseModel):
    window_start: dt.datetime = Field(..., description="时间桶起点（UTC）")
    total_requests: int = Field(..., description="该时间桶内总请求数")
    success_requests: int = Field(..., description="成功请求数")
    error_requests: int = Field(..., description="失败请求数")
    latency_avg_ms: float = Field(..., description="平均延迟（毫秒）")
    latency_p95_ms: float = Field(..., description="P95 延迟（毫秒）")
    latency_p99_ms: float = Field(..., description="P99 延迟（毫秒）")
    error_rate: float = Field(..., description="错误率 [0,1]")


class ProviderMetricsTimeSeries(BaseModel):
    provider_id: str
    logical_model: str
    time_range: str
    bucket: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    points: list[MetricsDataPoint] = Field(default_factory=list)


class ProviderMetricsSummary(BaseModel):
    provider_id: str
    logical_model: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    user_id: str | None = Field(
        None,
        description="用户 ID 过滤（如提供则仅统计该用户，默认全部用户）",
    )
    api_key_id: str | None = Field(
        None,
        description="API Key ID 过滤（如提供则仅统计该密钥，默认全部密钥）",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    error_rate: float
    latency_avg_ms: float | None = Field(
        None,
        description="平均延迟（毫秒），无请求时为 null",
    )


class UserMetricsSummary(BaseModel):
    user_id: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    error_rate: float
    latency_avg_ms: float | None = Field(
        None,
        description="平均延迟（毫秒），无请求时为 null",
    )


class APIKeyMetricsSummary(BaseModel):
    api_key_id: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    error_rate: float
    latency_avg_ms: float | None = Field(
        None,
        description="平均延迟（毫秒），无请求时为 null",
    )


class OverviewMetricsSummary(BaseModel):
    """
    仪表盘概览使用的全局汇总指标。

    - total_requests / success_requests / error_requests：当前时间范围内的总请求、成功数与失败数；
    - *_prev 字段：上一对比周期的同类指标（若无法计算则为 null）；
    - success_rate / success_rate_prev：成功率，范围 [0,1]。
    """

    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )

    total_requests: int
    success_requests: int
    error_requests: int
    success_rate: float

    total_requests_prev: int | None = Field(
        None,
        description="上一对比周期的总请求数，若不可用则为 null",
    )
    success_requests_prev: int | None = Field(
        None,
        description="上一对比周期的成功请求数，若不可用则为 null",
    )
    error_requests_prev: int | None = Field(
        None,
        description="上一对比周期的失败请求数，若不可用则为 null",
    )
    success_rate_prev: float | None = Field(
        None,
        description="上一对比周期的成功率 [0,1]，若不可用则为 null",
    )

    active_providers: int = Field(
        ...,
        description="当前时间范围内有流量的 Provider 数量",
    )
    active_providers_prev: int | None = Field(
        None,
        description="上一对比周期有流量的 Provider 数量，若不可用则为 null",
    )


class ActiveProviderMetrics(BaseModel):
    """
    单个 Provider 在给定时间范围内的聚合指标。
    """

    provider_id: str = Field(..., description="Provider ID，例如 openai")
    total_requests: int = Field(..., description="总请求数")
    success_requests: int = Field(..., description="成功请求数")
    error_requests: int = Field(..., description="失败请求数")
    success_rate: float = Field(..., description="成功率 [0,1]")
    latency_p95_ms: float | None = Field(
        None,
        description="P95 延迟（毫秒），无请求时为 null",
    )


class OverviewActiveProviders(BaseModel):
    """
    仪表盘概览页“活跃提供商”卡片使用的数据结构。
    """

    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    items: list[ActiveProviderMetrics] = Field(
        default_factory=list,
        description="按请求量排序的活跃 Provider 列表",
    )


class OverviewMetricsTimeSeries(BaseModel):
    """
    仪表盘概览页“近期活动”使用的全局时间序列。
    """

    time_range: str
    bucket: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    points: list[MetricsDataPoint] = Field(default_factory=list)


class UserOverviewMetricsSummary(BaseModel):
    """
    用户维度概览汇总指标。
    """

    scope: Literal["user"] = "user"
    user_id: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    success_rate: float
    total_requests_prev: int | None = Field(
        None,
        description="上一周期的总请求数，用于对比",
    )
    success_requests_prev: int | None = Field(None)
    error_requests_prev: int | None = Field(None)
    success_rate_prev: float | None = Field(None)
    active_providers: int
    active_providers_prev: int | None = Field(None)


class UserOverviewMetricsTimeSeries(BaseModel):
    """
    用户维度近期活动时间序列。
    """

    scope: Literal["user"] = "user"
    user_id: str
    time_range: str
    bucket: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    points: list[MetricsDataPoint] = Field(default_factory=list)


class UserActiveProviderMetrics(BaseModel):
    provider_id: str = Field(..., description="Provider ID")
    total_requests: int
    success_requests: int
    error_requests: int
    success_rate: float
    latency_p95_ms: float | None = Field(
        None,
        description="P95 延迟（毫秒），无请求时为 null",
    )


class UserOverviewActiveProviders(BaseModel):
    scope: Literal["user"] = "user"
    user_id: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    items: list[UserActiveProviderMetrics] = Field(default_factory=list)


class UserAppUsageMetrics(BaseModel):
    app_name: str = Field(
        ...,
        description="客户端 App 名称（由 X-Title/User-Agent/Referer 推断，可能被客户端伪造）",
    )
    total_requests: int = Field(..., description="总请求数（入口请求口径）")
    last_seen_at: dt.datetime | None = Field(
        None,
        description="最近一次出现的时间桶起点（UTC，分钟粒度）",
    )


class UserOverviewAppUsage(BaseModel):
    scope: Literal["user"] = "user"
    user_id: str
    time_range: str
    items: list[UserAppUsageMetrics] = Field(
        default_factory=list,
        description="按请求量降序排序的 App 使用排行",
    )


__all__ = [
    "APIKeyMetricsSummary",
    "ActiveProviderMetrics",
    "MetricsBucket",
    "MetricsDataPoint",
    "MetricsTimeRange",
    "OverviewActiveProviders",
    "OverviewMetricsSummary",
    "OverviewMetricsTimeSeries",
    "ProviderMetricsSummary",
    "ProviderMetricsTimeSeries",
    "UserMetricsSummary",
    "UserOverviewMetricsSummary",
    "UserOverviewMetricsTimeSeries",
    "UserActiveProviderMetrics",
    "UserOverviewActiveProviders",
    "UserAppUsageMetrics",
    "UserOverviewAppUsage",
]
