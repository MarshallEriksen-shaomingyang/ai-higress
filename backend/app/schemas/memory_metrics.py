"""Memory metrics schemas for API responses."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class MemoryMetricsKpis(BaseModel):
    """Memory system KPI summary."""

    time_range: str = Field(..., description="时间范围: today/7d/30d")

    # Request totals
    total_requests: int = Field(0, description="总请求数")
    retrieval_triggered: int = Field(0, description="触发检索次数")
    retrieval_skipped: int = Field(0, description="跳过检索次数")

    # Core rates
    trigger_rate: float = Field(0.0, description="检索触发率 (triggered / total)")
    hit_rate: float = Field(0.0, description="命中率 (hits / (hits + misses))")

    # Latency
    retrieval_latency_avg_ms: float = Field(0.0, description="平均检索延迟(ms)")
    retrieval_latency_p95_ms: float = Field(0.0, description="P95 检索延迟(ms)")

    # Hit/Miss counts
    memory_hits: int = Field(0, description="记忆命中数")
    memory_misses: int = Field(0, description="记忆未命中数")

    # Routing metrics
    routing_requests: int = Field(0, description="路由决策总数")
    routing_stored_user: int = Field(0, description="存储到用户维度")
    routing_stored_system: int = Field(0, description="存储到系统维度")
    routing_skipped: int = Field(0, description="跳过存储")

    # Session backlog
    session_count: int = Field(0, description="会话数")
    avg_backlog_per_session: float = Field(0.0, description="每会话平均积压批次")
    backlog_batches_max: int = Field(0, description="最大积压批次数")


class MemoryMetricsDataPoint(BaseModel):
    """Single data point for time series."""

    window_start: dt.datetime = Field(..., description="时间桶起点(UTC)")
    total_requests: int = Field(0)
    retrieval_triggered: int = Field(0)
    memory_hits: int = Field(0)
    memory_misses: int = Field(0)
    trigger_rate: float = Field(0.0)
    hit_rate: float = Field(0.0)
    retrieval_latency_avg_ms: float = Field(0.0)
    routing_requests: int = Field(0)
    avg_backlog_per_session: float = Field(0.0)


class MemoryMetricsPulse(BaseModel):
    """Time series data for memory metrics."""

    time_range: str
    granularity: str = Field("minute", description="数据粒度: minute/hour")
    points: list[MemoryMetricsDataPoint] = Field(default_factory=list)


class MemoryAlertThresholds(BaseModel):
    """Alert thresholds for memory metrics."""

    trigger_rate_low: float = Field(0.1, description="触发率低于此值告警")
    trigger_rate_high: float = Field(0.9, description="触发率高于此值告警")
    hit_rate_low: float = Field(0.3, description="命中率低于此值告警")
    latency_p95_high_ms: float = Field(500.0, description="P95延迟高于此值告警(ms)")
    backlog_per_session_high: float = Field(10.0, description="每会话积压高于此值告警")


class MemoryAlert(BaseModel):
    """Single alert for memory metrics."""

    alert_type: str = Field(..., description="告警类型: trigger_rate_low/hit_rate_low/latency_high/backlog_high")
    severity: Literal["warning", "critical"] = Field(..., description="严重程度")
    current_value: float = Field(..., description="当前值")
    threshold: float = Field(..., description="阈值")
    message: str = Field(..., description="告警消息")
    window_start: dt.datetime = Field(..., description="时间窗口")


class MemoryMetricsAlerts(BaseModel):
    """Active alerts for memory metrics."""

    time_range: str
    thresholds: MemoryAlertThresholds
    alerts: list[MemoryAlert] = Field(default_factory=list)


class MemoryMetricsDashboard(BaseModel):
    """Combined dashboard data for memory metrics."""

    kpis: MemoryMetricsKpis
    pulse: MemoryMetricsPulse
    alerts: MemoryMetricsAlerts


__all__ = [
    "MemoryAlert",
    "MemoryAlertThresholds",
    "MemoryMetricsAlerts",
    "MemoryMetricsDashboard",
    "MemoryMetricsDataPoint",
    "MemoryMetricsKpis",
    "MemoryMetricsPulse",
]
