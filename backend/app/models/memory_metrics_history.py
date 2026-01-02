"""Memory metrics history models for tracking memory retrieval and routing performance."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryMetricsHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Aggregated memory metrics snapshot over a time window.

    Tracks key memory system indicators:
    - Retrieval trigger rate: how often memory retrieval is triggered
    - Hit rate: how often retrieved memory is actually useful
    - Additional latency: overhead from memory operations
    - Backlog batches per session: identifies abnormal/cost spikes
    """

    __tablename__ = "memory_metrics_history"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "project_id",
            "window_start",
            name="uq_memory_metrics_history_bucket",
        ),
        Index(
            "ix_memory_metrics_history_window_start",
            "window_start",
        ),
        Index(
            "ix_memory_metrics_history_user_window",
            "user_id",
            "window_start",
        ),
        Index(
            "ix_memory_metrics_history_project_window",
            "project_id",
            "window_start",
        ),
    )

    # Dimension fields
    user_id: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    project_id: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Aggregation window (default 60s bucket)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_duration: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("60"),  # seconds
    )

    # ===================
    # Core Metrics
    # ===================

    # Request counts
    total_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    # Retrieval metrics
    retrieval_triggered: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Number of times memory retrieval was triggered"
    )
    retrieval_skipped: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Number of times retrieval was skipped (no hint, short query, etc.)"
    )
    retrieval_success: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Successful retrievals (found relevant memory)"
    )
    retrieval_empty: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Retrievals that returned empty (no matching memory)"
    )
    retrieval_error: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Retrieval failures (errors, timeouts)"
    )

    # Hit rate metrics (memory was actually used/helpful)
    memory_hits: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Retrieved memory was above score threshold"
    )
    memory_misses: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Retrieved memory was below score threshold"
    )

    # Latency metrics (in milliseconds)
    retrieval_latency_sum_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
        comment="Sum of retrieval latencies for averaging"
    )
    retrieval_latency_avg_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )
    retrieval_latency_p50_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )
    retrieval_latency_p95_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )
    retrieval_latency_p99_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )

    # Query rewrite metrics
    rewrite_triggered: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Number of times query rewriting was triggered"
    )
    rewrite_success: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
    )
    rewrite_latency_sum_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )

    # Embedding metrics
    embedding_requests: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
    )
    embedding_latency_sum_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )

    # Vector search metrics
    vector_search_requests: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
    )
    vector_search_latency_sum_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )
    raw_hits_sum: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Sum of raw hits before filtering"
    )
    valid_hits_sum: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Sum of valid hits after score filtering"
    )

    # Memory routing metrics (write path)
    routing_requests: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Number of memory routing decisions"
    )
    routing_stored_user: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Stored to user memory scope"
    )
    routing_stored_system: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Stored to system memory scope"
    )
    routing_skipped: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Routing decided not to store"
    )
    routing_latency_sum_ms: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
    )

    # Session backlog metrics (for cost spike detection)
    session_count: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Number of unique sessions in this window"
    )
    backlog_batches_sum: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Sum of pending batch counts across sessions"
    )
    backlog_batches_max: Mapped[int] = Column(
        Integer, nullable=False, server_default=text("0"),
        comment="Max pending batches in any single session"
    )

    # Computed rates (for convenience, updated on flush)
    trigger_rate: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
        comment="retrieval_triggered / total_requests"
    )
    hit_rate: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
        comment="memory_hits / (memory_hits + memory_misses)"
    )
    avg_backlog_per_session: Mapped[float] = Column(
        Float, nullable=False, server_default=text("0"),
        comment="backlog_batches_sum / session_count"
    )


class MemoryMetricsHourly(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hourly rollup of memory metrics for long-term storage."""

    __tablename__ = "memory_metrics_hourly"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "project_id",
            "window_start",
            name="uq_memory_metrics_hourly_bucket",
        ),
        Index("ix_memory_metrics_hourly_window_start", "window_start"),
    )

    user_id: Mapped[UUID | None] = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    project_id: Mapped[UUID | None] = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    window_start = Column(DateTime(timezone=True), nullable=False)
    window_duration: Mapped[int] = Column(Integer, nullable=False, server_default=text("3600"))

    # Aggregated counts
    total_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    retrieval_triggered: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    retrieval_success: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    retrieval_empty: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    retrieval_error: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    memory_hits: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    memory_misses: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    # Aggregated latencies
    retrieval_latency_avg_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    retrieval_latency_p95_ms: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))

    # Routing aggregates
    routing_requests: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    routing_stored_user: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    routing_stored_system: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    # Session/backlog aggregates
    session_count: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    backlog_batches_sum: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    backlog_batches_max: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))

    # Computed rates
    trigger_rate: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    hit_rate: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))
    avg_backlog_per_session: Mapped[float] = Column(Float, nullable=False, server_default=text("0"))


__all__ = ["MemoryMetricsHistory", "MemoryMetricsHourly"]
