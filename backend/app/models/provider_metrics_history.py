from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from uuid import UUID

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderRoutingMetricsHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Aggregated routing metrics snapshot for a provider/logical_model over a time window.

    This table is intended for analytics 和可视化（报表/图表），
    与 Redis 中的实时 RoutingMetrics 互补。
    """

    __tablename__ = "provider_routing_metrics_history"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
            name="uq_provider_routing_metrics_history_bucket",
        ),
        Index(
            "ix_provider_routing_metrics_history_provider_logical_window",
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "window_start",
        ),
        Index(
            "ix_provider_routing_metrics_history_user_window",
            "user_id",
            "window_start",
        ),
        Index(
            "ix_provider_routing_metrics_history_api_key_window",
            "api_key_id",
            "window_start",
        ),
    )

    provider_id: Mapped[str] = Column(String(50), nullable=False, index=True)
    logical_model: Mapped[str] = Column(String(100), nullable=False, index=True)

    # 细分维度：传输模式（HTTP / SDK）以及是否流式。
    transport: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'http'"),
    )
    is_stream: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )

    # 细分维度：调用的用户和 API Key（若可用）。
    user_id: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    api_key_id: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # 聚合窗口信息（例如按分钟/5 分钟落盘）
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_duration: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("60"),  # 单位：秒，默认 60s 窗口
    )

    # 与 app.schemas.RoutingMetrics 对齐的核心指标字段（按时间桶聚合）
    # 为了后续扩展，这里既记录计数，也记录简单的平均 / 百分位延迟。
    total_requests_1m: Mapped[int] = Column(Integer, nullable=False)
    success_requests: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    error_requests: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    latency_avg_ms: Mapped[float] = Column(
        Float,
        nullable=False,
        server_default=text("0"),
    )
    latency_p50_ms: Mapped[float] = Column(
        Float,
        nullable=False,
        server_default=text("0"),
    )
    latency_p95_ms: Mapped[float] = Column(Float, nullable=False)
    latency_p99_ms: Mapped[float] = Column(Float, nullable=False)

    error_rate: Mapped[float] = Column(Float, nullable=False)
    success_qps_1m: Mapped[float] = Column(Float, nullable=False)
    status: Mapped[str] = Column(String(16), nullable=False)

    # Error breakdown counts (for stacked error charts).
    error_4xx_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_5xx_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_429_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_timeout_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    # Token aggregates (do not depend on billing/pricing presence).
    input_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    output_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    token_estimated_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

class ProviderRoutingMetricsHourly(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Hourly rollup of provider routing metrics.

    Written by Celery tasks to reduce query cost for 7d/30d dashboards.
    """

    __tablename__ = "provider_routing_metrics_hourly"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
            name="uq_provider_routing_metrics_hourly_bucket",
        ),
        Index(
            "ix_provider_routing_metrics_hourly_provider_logical_window",
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "window_start",
        ),
        Index(
            "ix_provider_routing_metrics_hourly_user_window",
            "user_id",
            "window_start",
        ),
    )

    provider_id: Mapped[str] = Column(String(50), nullable=False, index=True)
    logical_model: Mapped[str] = Column(String(100), nullable=False, index=True)
    transport: Mapped[str] = Column(String(16), nullable=False, server_default=text("'http'"))
    is_stream: Mapped[bool] = Column(Boolean, nullable=False, server_default=text("FALSE"))

    user_id: Mapped[UUID | None] = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    api_key_id: Mapped[UUID | None] = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_duration: Mapped[int] = Column(Integer, nullable=False, server_default=text("3600"))

    total_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    success_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    latency_avg_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    latency_p50_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    latency_p95_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    latency_p99_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))

    error_rate: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    success_qps: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    status: Mapped[str] = Column(String(16), nullable=False, server_default=text("'unknown'"))

    error_4xx_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_5xx_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_429_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_timeout_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    input_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    output_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    token_estimated_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))


class ProviderRoutingMetricsDaily(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Daily rollup of provider routing metrics."""

    __tablename__ = "provider_routing_metrics_daily"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
            name="uq_provider_routing_metrics_daily_bucket",
        ),
        Index(
            "ix_provider_routing_metrics_daily_provider_logical_window",
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "window_start",
        ),
        Index(
            "ix_provider_routing_metrics_daily_user_window",
            "user_id",
            "window_start",
        ),
    )

    provider_id: Mapped[str] = Column(String(50), nullable=False, index=True)
    logical_model: Mapped[str] = Column(String(100), nullable=False, index=True)
    transport: Mapped[str] = Column(String(16), nullable=False, server_default=text("'http'"))
    is_stream: Mapped[bool] = Column(Boolean, nullable=False, server_default=text("FALSE"))

    user_id: Mapped[UUID | None] = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    api_key_id: Mapped[UUID | None] = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_duration: Mapped[int] = Column(Integer, nullable=False, server_default=text("86400"))

    total_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    success_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    latency_avg_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    latency_p50_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    latency_p95_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    latency_p99_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))

    error_rate: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    success_qps: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    status: Mapped[str] = Column(String(16), nullable=False, server_default=text("'unknown'"))

    error_4xx_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_5xx_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_429_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_timeout_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    input_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    output_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    token_estimated_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))


__all__ = [
    "ProviderRoutingMetricsDaily",
    "ProviderRoutingMetricsHistory",
    "ProviderRoutingMetricsHourly",
]
