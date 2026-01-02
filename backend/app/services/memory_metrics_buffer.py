"""
Memory metrics buffer and recorder.

Provides in-memory buffering and periodic DB flush for memory system metrics,
including retrieval, routing, and latency tracking.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import random
import threading
from dataclasses import dataclass, field
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import Float, cast
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models.memory_metrics_history import MemoryMetricsHistory

logger = logging.getLogger(__name__)

# Default bucket size in seconds
BucketSeconds = int


@dataclass
class MemoryMetricsStats:
    """In-memory stats accumulator for a single time bucket."""

    # Request counts
    total_requests: int = 0

    # Retrieval metrics
    retrieval_triggered: int = 0
    retrieval_skipped: int = 0
    retrieval_success: int = 0
    retrieval_empty: int = 0
    retrieval_error: int = 0

    # Hit/miss tracking
    memory_hits: int = 0
    memory_misses: int = 0

    # Latency tracking
    retrieval_latency_sum_ms: float = 0.0
    retrieval_latency_samples: list[float] = field(default_factory=list)

    # Query rewrite metrics
    rewrite_triggered: int = 0
    rewrite_success: int = 0
    rewrite_latency_sum_ms: float = 0.0

    # Embedding metrics
    embedding_requests: int = 0
    embedding_latency_sum_ms: float = 0.0

    # Vector search metrics
    vector_search_requests: int = 0
    vector_search_latency_sum_ms: float = 0.0
    raw_hits_sum: int = 0
    valid_hits_sum: int = 0

    # Routing metrics (write path)
    routing_requests: int = 0
    routing_stored_user: int = 0
    routing_stored_system: int = 0
    routing_skipped: int = 0
    routing_latency_sum_ms: float = 0.0

    # Session/backlog tracking
    session_ids: set[str] = field(default_factory=set)
    backlog_batches_sum: int = 0
    backlog_batches_max: int = 0

    def record_retrieval(
        self,
        *,
        triggered: bool,
        success: bool | None,
        latency_ms: float,
        raw_hits: int = 0,
        valid_hits: int = 0,
        sample_limit: int = 100,
    ) -> None:
        """Record a retrieval operation."""
        self.total_requests += 1

        if not triggered:
            self.retrieval_skipped += 1
            return

        self.retrieval_triggered += 1

        if success is None:
            # Error case
            self.retrieval_error += 1
        elif success:
            self.retrieval_success += 1
            # Track hits/misses based on valid_hits
            if valid_hits > 0:
                self.memory_hits += 1
            else:
                self.memory_misses += 1
        else:
            self.retrieval_empty += 1
            self.memory_misses += 1

        # Latency tracking
        self.retrieval_latency_sum_ms += latency_ms
        if sample_limit > 0:
            if len(self.retrieval_latency_samples) < sample_limit:
                self.retrieval_latency_samples.append(latency_ms)
            else:
                # Reservoir sampling
                replace_at = random.randint(0, self.retrieval_triggered - 1)
                if replace_at < sample_limit:
                    self.retrieval_latency_samples[replace_at] = latency_ms

        # Vector search stats
        if triggered:
            self.vector_search_requests += 1
            self.raw_hits_sum += raw_hits
            self.valid_hits_sum += valid_hits

    def record_rewrite(self, *, triggered: bool, success: bool, latency_ms: float) -> None:
        """Record a query rewrite operation."""
        if not triggered:
            return
        self.rewrite_triggered += 1
        if success:
            self.rewrite_success += 1
        self.rewrite_latency_sum_ms += latency_ms

    def record_embedding(self, *, latency_ms: float) -> None:
        """Record an embedding operation."""
        self.embedding_requests += 1
        self.embedding_latency_sum_ms += latency_ms

    def record_routing(
        self,
        *,
        scope: str,  # "user", "system", "none"
        latency_ms: float,
    ) -> None:
        """Record a routing decision."""
        self.routing_requests += 1
        self.routing_latency_sum_ms += latency_ms

        if scope == "user":
            self.routing_stored_user += 1
        elif scope == "system":
            self.routing_stored_system += 1
        else:
            self.routing_skipped += 1

    def record_session_backlog(self, *, session_id: str, pending_batches: int) -> None:
        """Record session backlog for cost spike detection."""
        self.session_ids.add(session_id)
        self.backlog_batches_sum += pending_batches
        self.backlog_batches_max = max(self.backlog_batches_max, pending_batches)

    def _percentile(self, samples: list[float], percentile: float) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        if len(ordered) == 1:
            return ordered[0]
        k = (len(ordered) - 1) * percentile
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return ordered[int(k)]
        return ordered[f] + (ordered[c] - ordered[f]) * (k - f)

    def retrieval_latency_avg(self) -> float:
        if self.retrieval_triggered == 0:
            return 0.0
        return self.retrieval_latency_sum_ms / self.retrieval_triggered

    def retrieval_latency_p50(self) -> float:
        return self._percentile(self.retrieval_latency_samples, 0.5)

    def retrieval_latency_p95(self) -> float:
        return self._percentile(self.retrieval_latency_samples, 0.95)

    def retrieval_latency_p99(self) -> float:
        return self._percentile(self.retrieval_latency_samples, 0.99)

    def trigger_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.retrieval_triggered / self.total_requests

    def hit_rate(self) -> float:
        total_hits_misses = self.memory_hits + self.memory_misses
        if total_hits_misses == 0:
            return 0.0
        return self.memory_hits / total_hits_misses

    def avg_backlog_per_session(self) -> float:
        if not self.session_ids:
            return 0.0
        return self.backlog_batches_sum / len(self.session_ids)


class MemoryMetricsKey(NamedTuple):
    """Key for bucketing memory metrics."""

    user_id: UUID | None
    project_id: UUID | None
    window_start: dt.datetime
    bucket_seconds: BucketSeconds


class BufferedMemoryMetricsRecorder:
    """In-memory memory metrics aggregator with periodic DB flush."""

    def __init__(
        self,
        *,
        flush_interval_seconds: int = 60,
        latency_sample_size: int = 100,
        max_buffered_buckets: int = 1000,
    ) -> None:
        self.flush_interval_seconds = flush_interval_seconds
        self.latency_sample_size = latency_sample_size
        self.max_buffered_buckets = max_buffered_buckets

        self._buffer: dict[MemoryMetricsKey, MemoryMetricsStats] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._flush_thread and self._flush_thread.is_alive():
            return

        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, name="memory-metrics-flusher", daemon=True
        )
        self._flush_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=1.0)

    def _get_or_create_stats(
        self,
        user_id: UUID | None,
        project_id: UUID | None,
        window_start: dt.datetime,
        bucket_seconds: BucketSeconds = 60,
    ) -> MemoryMetricsStats:
        """Get or create stats for a key, triggering flush if buffer is full."""
        key = MemoryMetricsKey(
            user_id=user_id,
            project_id=project_id,
            window_start=window_start,
            bucket_seconds=bucket_seconds,
        )

        with self._lock:
            stats = self._buffer.get(key)
            if stats is None:
                stats = MemoryMetricsStats()
                self._buffer[key] = stats

            if len(self._buffer) >= self.max_buffered_buckets:
                # Trigger async flush to avoid memory growth
                threading.Thread(target=self.flush, daemon=True).start()

            return stats

    def record_retrieval(
        self,
        *,
        user_id: UUID | None,
        project_id: UUID | None,
        window_start: dt.datetime,
        triggered: bool,
        success: bool | None,
        latency_ms: float,
        raw_hits: int = 0,
        valid_hits: int = 0,
    ) -> None:
        """Record a memory retrieval operation."""
        stats = self._get_or_create_stats(user_id, project_id, window_start)
        with self._lock:
            stats.record_retrieval(
                triggered=triggered,
                success=success,
                latency_ms=latency_ms,
                raw_hits=raw_hits,
                valid_hits=valid_hits,
                sample_limit=self.latency_sample_size,
            )

    def record_rewrite(
        self,
        *,
        user_id: UUID | None,
        project_id: UUID | None,
        window_start: dt.datetime,
        triggered: bool,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a query rewrite operation."""
        stats = self._get_or_create_stats(user_id, project_id, window_start)
        with self._lock:
            stats.record_rewrite(triggered=triggered, success=success, latency_ms=latency_ms)

    def record_embedding(
        self,
        *,
        user_id: UUID | None,
        project_id: UUID | None,
        window_start: dt.datetime,
        latency_ms: float,
    ) -> None:
        """Record an embedding operation."""
        stats = self._get_or_create_stats(user_id, project_id, window_start)
        with self._lock:
            stats.record_embedding(latency_ms=latency_ms)

    def record_routing(
        self,
        *,
        user_id: UUID | None,
        project_id: UUID | None,
        window_start: dt.datetime,
        scope: str,
        latency_ms: float,
    ) -> None:
        """Record a routing decision."""
        stats = self._get_or_create_stats(user_id, project_id, window_start)
        with self._lock:
            stats.record_routing(scope=scope, latency_ms=latency_ms)

    def record_session_backlog(
        self,
        *,
        user_id: UUID | None,
        project_id: UUID | None,
        window_start: dt.datetime,
        session_id: str,
        pending_batches: int,
    ) -> None:
        """Record session backlog for cost spike detection."""
        stats = self._get_or_create_stats(user_id, project_id, window_start)
        with self._lock:
            stats.record_session_backlog(session_id=session_id, pending_batches=pending_batches)

    def flush(self) -> int:
        """Flush buffered metrics to database."""
        items = self._drain_buffer()
        if not items:
            return 0

        session = SessionLocal()
        flushed = 0
        try:
            for key, stats in items:
                stmt = self._build_upsert_stmt(key, stats)
                session.execute(stmt)
                flushed += 1
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to flush buffered memory metrics")
        finally:
            session.close()
        return flushed

    def _drain_buffer(self) -> list[tuple[MemoryMetricsKey, MemoryMetricsStats]]:
        with self._lock:
            if not self._buffer:
                return []
            items = list(self._buffer.items())
            self._buffer = {}
            return items

    def _flush_loop(self) -> None:
        while not self._stop_event.wait(self.flush_interval_seconds):
            try:
                flushed = self.flush()
                if flushed:
                    logger.debug("Flushed %d buffered memory metric buckets", flushed)
            except Exception:
                logger.exception("Unexpected error while flushing memory metrics buffer")

    def _build_upsert_stmt(self, key: MemoryMetricsKey, stats: MemoryMetricsStats):
        """Build PostgreSQL upsert statement for memory metrics."""
        session_count = len(stats.session_ids)

        base_insert = insert(MemoryMetricsHistory).values(
            user_id=key.user_id,
            project_id=key.project_id,
            window_start=key.window_start,
            window_duration=key.bucket_seconds,
            # Counts
            total_requests=stats.total_requests,
            retrieval_triggered=stats.retrieval_triggered,
            retrieval_skipped=stats.retrieval_skipped,
            retrieval_success=stats.retrieval_success,
            retrieval_empty=stats.retrieval_empty,
            retrieval_error=stats.retrieval_error,
            memory_hits=stats.memory_hits,
            memory_misses=stats.memory_misses,
            # Latency
            retrieval_latency_sum_ms=stats.retrieval_latency_sum_ms,
            retrieval_latency_avg_ms=stats.retrieval_latency_avg(),
            retrieval_latency_p50_ms=stats.retrieval_latency_p50(),
            retrieval_latency_p95_ms=stats.retrieval_latency_p95(),
            retrieval_latency_p99_ms=stats.retrieval_latency_p99(),
            # Rewrite
            rewrite_triggered=stats.rewrite_triggered,
            rewrite_success=stats.rewrite_success,
            rewrite_latency_sum_ms=stats.rewrite_latency_sum_ms,
            # Embedding
            embedding_requests=stats.embedding_requests,
            embedding_latency_sum_ms=stats.embedding_latency_sum_ms,
            # Vector search
            vector_search_requests=stats.vector_search_requests,
            vector_search_latency_sum_ms=stats.vector_search_latency_sum_ms,
            raw_hits_sum=stats.raw_hits_sum,
            valid_hits_sum=stats.valid_hits_sum,
            # Routing
            routing_requests=stats.routing_requests,
            routing_stored_user=stats.routing_stored_user,
            routing_stored_system=stats.routing_stored_system,
            routing_skipped=stats.routing_skipped,
            routing_latency_sum_ms=stats.routing_latency_sum_ms,
            # Session/backlog
            session_count=session_count,
            backlog_batches_sum=stats.backlog_batches_sum,
            backlog_batches_max=stats.backlog_batches_max,
            # Computed rates
            trigger_rate=stats.trigger_rate(),
            hit_rate=stats.hit_rate(),
            avg_backlog_per_session=stats.avg_backlog_per_session(),
        )

        # Build update values for conflict
        new_total = MemoryMetricsHistory.total_requests + stats.total_requests
        new_triggered = MemoryMetricsHistory.retrieval_triggered + stats.retrieval_triggered
        new_hits = MemoryMetricsHistory.memory_hits + stats.memory_hits
        new_misses = MemoryMetricsHistory.memory_misses + stats.memory_misses
        new_session = MemoryMetricsHistory.session_count + session_count

        existing_latency_sum = MemoryMetricsHistory.retrieval_latency_sum_ms
        new_latency_sum = existing_latency_sum + stats.retrieval_latency_sum_ms

        return base_insert.on_conflict_do_update(
            constraint="uq_memory_metrics_history_bucket",
            set_={
                # Counts
                "total_requests": new_total,
                "retrieval_triggered": new_triggered,
                "retrieval_skipped": MemoryMetricsHistory.retrieval_skipped + stats.retrieval_skipped,
                "retrieval_success": MemoryMetricsHistory.retrieval_success + stats.retrieval_success,
                "retrieval_empty": MemoryMetricsHistory.retrieval_empty + stats.retrieval_empty,
                "retrieval_error": MemoryMetricsHistory.retrieval_error + stats.retrieval_error,
                "memory_hits": new_hits,
                "memory_misses": new_misses,
                # Latency - weighted average
                "retrieval_latency_sum_ms": new_latency_sum,
                "retrieval_latency_avg_ms": new_latency_sum / cast(new_triggered, Float),
                "retrieval_latency_p50_ms": (
                    (MemoryMetricsHistory.retrieval_latency_p50_ms * MemoryMetricsHistory.retrieval_triggered
                     + stats.retrieval_latency_p50() * stats.retrieval_triggered)
                    / cast(new_triggered, Float)
                ),
                "retrieval_latency_p95_ms": (
                    (MemoryMetricsHistory.retrieval_latency_p95_ms * MemoryMetricsHistory.retrieval_triggered
                     + stats.retrieval_latency_p95() * stats.retrieval_triggered)
                    / cast(new_triggered, Float)
                ),
                "retrieval_latency_p99_ms": (
                    (MemoryMetricsHistory.retrieval_latency_p99_ms * MemoryMetricsHistory.retrieval_triggered
                     + stats.retrieval_latency_p99() * stats.retrieval_triggered)
                    / cast(new_triggered, Float)
                ),
                # Rewrite
                "rewrite_triggered": MemoryMetricsHistory.rewrite_triggered + stats.rewrite_triggered,
                "rewrite_success": MemoryMetricsHistory.rewrite_success + stats.rewrite_success,
                "rewrite_latency_sum_ms": MemoryMetricsHistory.rewrite_latency_sum_ms + stats.rewrite_latency_sum_ms,
                # Embedding
                "embedding_requests": MemoryMetricsHistory.embedding_requests + stats.embedding_requests,
                "embedding_latency_sum_ms": MemoryMetricsHistory.embedding_latency_sum_ms + stats.embedding_latency_sum_ms,
                # Vector search
                "vector_search_requests": MemoryMetricsHistory.vector_search_requests + stats.vector_search_requests,
                "vector_search_latency_sum_ms": MemoryMetricsHistory.vector_search_latency_sum_ms + stats.vector_search_latency_sum_ms,
                "raw_hits_sum": MemoryMetricsHistory.raw_hits_sum + stats.raw_hits_sum,
                "valid_hits_sum": MemoryMetricsHistory.valid_hits_sum + stats.valid_hits_sum,
                # Routing
                "routing_requests": MemoryMetricsHistory.routing_requests + stats.routing_requests,
                "routing_stored_user": MemoryMetricsHistory.routing_stored_user + stats.routing_stored_user,
                "routing_stored_system": MemoryMetricsHistory.routing_stored_system + stats.routing_stored_system,
                "routing_skipped": MemoryMetricsHistory.routing_skipped + stats.routing_skipped,
                "routing_latency_sum_ms": MemoryMetricsHistory.routing_latency_sum_ms + stats.routing_latency_sum_ms,
                # Session/backlog
                "session_count": new_session,
                "backlog_batches_sum": MemoryMetricsHistory.backlog_batches_sum + stats.backlog_batches_sum,
                "backlog_batches_max": MemoryMetricsHistory.backlog_batches_max + stats.backlog_batches_max,
                # Computed rates
                "trigger_rate": cast(new_triggered, Float) / cast(new_total, Float),
                "hit_rate": cast(new_hits, Float) / cast(new_hits + new_misses, Float),
                "avg_backlog_per_session": (
                    (MemoryMetricsHistory.backlog_batches_sum + stats.backlog_batches_sum)
                    / cast(new_session, Float)
                ),
            },
        )


# Singleton instance
_memory_metrics_recorder: BufferedMemoryMetricsRecorder | None = None
_memory_metrics_lock = threading.Lock()


def get_memory_metrics_recorder() -> BufferedMemoryMetricsRecorder:
    """Get or create the global memory metrics recorder."""
    global _memory_metrics_recorder
    if _memory_metrics_recorder is None:
        with _memory_metrics_lock:
            if _memory_metrics_recorder is None:
                _memory_metrics_recorder = BufferedMemoryMetricsRecorder()
    return _memory_metrics_recorder


def start_memory_metrics_recorder() -> None:
    """Start the global memory metrics recorder."""
    recorder = get_memory_metrics_recorder()
    recorder.start()


def shutdown_memory_metrics_recorder() -> None:
    """Shutdown the global memory metrics recorder."""
    global _memory_metrics_recorder
    if _memory_metrics_recorder is not None:
        _memory_metrics_recorder.shutdown()


def ensure_memory_metrics_started() -> None:
    """Ensure the memory metrics recorder is started (idempotent)."""
    start_memory_metrics_recorder()


def shutdown_memory_metrics_buffer(*, flush: bool = True) -> None:
    """Shutdown the memory metrics buffer, optionally flushing first."""
    global _memory_metrics_recorder
    if _memory_metrics_recorder is not None:
        if flush:
            try:
                _memory_metrics_recorder.flush()
            except Exception:
                logger.exception("Failed to flush memory metrics during shutdown")
        _memory_metrics_recorder.shutdown()


__all__ = [
    "BufferedMemoryMetricsRecorder",
    "MemoryMetricsKey",
    "MemoryMetricsStats",
    "get_memory_metrics_recorder",
    "start_memory_metrics_recorder",
    "shutdown_memory_metrics_recorder",
    "ensure_memory_metrics_started",
    "shutdown_memory_metrics_buffer",
]
