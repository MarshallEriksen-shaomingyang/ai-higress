from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Column, Float, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from app.db.types import UTCDateTime

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AggregateRoutingMetrics(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Offline-recalculated metrics for coarse windows (e.g., 5m/1h).

    The table is populated by offline jobs that merge minute-level buckets
    from ``provider_routing_metrics_history`` and recompute percentiles/error
    rate with higher accuracy. Records are uniquely identified by the
    combination of provider/logical_model + transport/is_stream + user/API key
    + window start/duration.
    """

    __tablename__ = "aggregate_metrics"
    __table_args__ = (
        Index(
            "ix_aggregate_metrics_provider_logical_window",
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
        ),
        UniqueConstraint(
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
            "window_duration",
            name="uq_aggregate_metrics_bucket",
        ),
    )

    provider_id: Mapped[str] = Column(String(50), nullable=False, index=True)
    logical_model: Mapped[str] = Column(String(100), nullable=False, index=True)

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

    window_start = Column(UTCDateTime(), nullable=False, index=True)
    window_duration: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("300"),
    )

    total_requests: Mapped[int] = Column(Integer, nullable=False)
    success_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    error_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    latency_p50_ms: Mapped[float] = Column(Float, nullable=False)
    latency_p90_ms: Mapped[float] = Column(Float, nullable=False)
    latency_p95_ms: Mapped[float] = Column(Float, nullable=False)
    latency_p99_ms: Mapped[float] = Column(Float, nullable=False)

    error_rate: Mapped[float] = Column(Float, nullable=False)
    success_qps: Mapped[float] = Column(Float, nullable=False)
    status: Mapped[str] = Column(String(16), nullable=False)

    recalculated_at = Column(UTCDateTime(), nullable=False, server_default=func.now())
    source_version: Mapped[str] = Column(String(32), nullable=False, server_default=text("'offline-recalc'"))


__all__ = ["AggregateRoutingMetrics"]
