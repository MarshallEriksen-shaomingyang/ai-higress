from __future__ import annotations

import datetime as dt
import math
import random
import threading
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Float, cast
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.logging_config import logger
from app.models import ProviderRoutingMetricsHistory, UserRoutingMetricsHistory

BucketSeconds = int


@dataclass(frozen=True)
class MetricsKey:
    provider_id: str
    logical_model: str
    transport: str
    is_stream: bool
    user_id: UUID | None
    api_key_id: UUID | None
    window_start: dt.datetime
    bucket_seconds: BucketSeconds


@dataclass
class MetricsStats:
    total_requests: int = 0
    success_requests: int = 0
    error_requests: int = 0
    error_4xx_requests: int = 0
    error_5xx_requests: int = 0
    error_429_requests: int = 0
    error_timeout_requests: int = 0
    latency_sum_ms: float = 0.0
    latency_samples: list[float] = field(default_factory=list)

    def record(
        self,
        *,
        success: bool,
        latency_ms: float,
        sample_limit: int,
        error_kind: str | None = None,
    ) -> None:
        self.total_requests += 1
        if success:
            self.success_requests += 1
        else:
            self.error_requests += 1
            if error_kind == "429":
                self.error_429_requests += 1
            elif error_kind == "4xx":
                self.error_4xx_requests += 1
            elif error_kind == "5xx":
                self.error_5xx_requests += 1
            elif error_kind == "timeout":
                self.error_timeout_requests += 1

        self.latency_sum_ms += latency_ms
        if sample_limit <= 0:
            return

        if len(self.latency_samples) < sample_limit:
            self.latency_samples.append(latency_ms)
        else:
            # Reservoir sampling：保持样本数量稳定。
            replace_at = random.randint(0, self.total_requests - 1)
            if replace_at < sample_limit:
                self.latency_samples[replace_at] = latency_ms

    def latency_avg(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.latency_sum_ms / self.total_requests

    def _percentile(self, percentile: float) -> float:
        if not self.latency_samples:
            return self.latency_avg()
        ordered = sorted(self.latency_samples)
        if len(ordered) == 1:
            return ordered[0]
        k = (len(ordered) - 1) * percentile
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return ordered[int(k)]
        return ordered[f] + (ordered[c] - ordered[f]) * (k - f)

    def latency_p95(self) -> float:
        return self._percentile(0.95)

    def latency_p99(self) -> float:
        return self._percentile(0.99)

    def latency_p50(self) -> float:
        return self._percentile(0.5)


class BufferedMetricsRecorder:
    """In-memory metrics aggregator with periodic DB flush."""

    def __init__(
        self,
        *,
        flush_interval_seconds: int,
        latency_sample_size: int,
        max_buffered_buckets: int,
        success_sample_rate: float,
    ) -> None:
        self.flush_interval_seconds = flush_interval_seconds
        self.latency_sample_size = latency_sample_size
        self.max_buffered_buckets = max_buffered_buckets
        self.success_sample_rate = max(0.0, min(1.0, success_sample_rate))

        self._buffer: dict[MetricsKey, MetricsStats] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._flush_thread and self._flush_thread.is_alive():
            return

        self._flush_thread = threading.Thread(
            target=self._flush_loop, name="metrics-buffer-flusher", daemon=True
        )
        self._flush_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=1.0)

    def record_sample(
        self,
        *,
        provider_id: str,
        logical_model: str,
        transport: str,
        is_stream: bool,
        user_id: UUID | None,
        api_key_id: UUID | None,
        window_start: dt.datetime,
        bucket_seconds: BucketSeconds,
        success: bool,
        latency_ms: float,
        error_kind: str | None = None,
    ) -> None:
        if success and self.success_sample_rate < 1.0:
            if random.random() > self.success_sample_rate:
                return

        key = MetricsKey(
            provider_id=provider_id,
            logical_model=logical_model,
            transport=transport,
            is_stream=is_stream,
            user_id=user_id,
            api_key_id=api_key_id,
            window_start=window_start,
            bucket_seconds=bucket_seconds,
        )

        with self._lock:
            stats = self._buffer.get(key) or MetricsStats()
            stats.record(
                success=success,
                latency_ms=latency_ms,
                sample_limit=self.latency_sample_size,
                error_kind=error_kind,
            )
            self._buffer[key] = stats

            if len(self._buffer) >= self.max_buffered_buckets:
                # 触发一次异步刷新，避免内存无限增长。
                threading.Thread(target=self.flush, daemon=True).start()

    def flush(self) -> int:
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
            logger.exception("Failed to flush buffered routing metrics")
        finally:
            session.close()
        return flushed

    def _drain_buffer(self) -> list[tuple[MetricsKey, MetricsStats]]:
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
                    logger.debug("Flushed %d buffered metric buckets", flushed)
            except Exception:
                logger.exception("Unexpected error while flushing metrics buffer")

    @staticmethod
    def _status_from_error_rate(error_rate: float) -> str:
        if error_rate >= 0.5:
            return "unhealthy"
        if error_rate >= 0.2:
            return "degraded"
        return "healthy"

    def _build_upsert_stmt(self, key: MetricsKey, stats: MetricsStats):
        total_requests = stats.total_requests
        success_requests = stats.success_requests
        error_requests = stats.error_requests

        latency_avg = stats.latency_avg()
        latency_p50 = stats.latency_p50()
        latency_p95 = stats.latency_p95()
        latency_p99 = stats.latency_p99()
        error_rate = (error_requests / total_requests) if total_requests else 0.0
        success_qps = success_requests / key.bucket_seconds if key.bucket_seconds else 0.0
        status = self._status_from_error_rate(error_rate)

        base_insert = insert(ProviderRoutingMetricsHistory).values(
            provider_id=key.provider_id,
            logical_model=key.logical_model,
            transport=key.transport,
            is_stream=key.is_stream,
            user_id=key.user_id,
            api_key_id=key.api_key_id,
            window_start=key.window_start,
            window_duration=key.bucket_seconds,
            total_requests_1m=total_requests,
            success_requests=success_requests,
            error_requests=error_requests,
            latency_avg_ms=latency_avg,
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            error_rate=error_rate,
            success_qps_1m=success_qps,
            status=status,
            error_4xx_requests=stats.error_4xx_requests,
            error_5xx_requests=stats.error_5xx_requests,
            error_429_requests=stats.error_429_requests,
            error_timeout_requests=stats.error_timeout_requests,
        )

        new_total = ProviderRoutingMetricsHistory.total_requests_1m + total_requests
        new_success = ProviderRoutingMetricsHistory.success_requests + success_requests
        new_error = ProviderRoutingMetricsHistory.error_requests + error_requests

        existing_latency_sum = (
            ProviderRoutingMetricsHistory.latency_avg_ms
            * ProviderRoutingMetricsHistory.total_requests_1m
        )

        return base_insert.on_conflict_do_update(
            constraint="uq_provider_routing_metrics_history_bucket",
            set_={
                "total_requests_1m": new_total,
                "success_requests": new_success,
                "error_requests": new_error,
                "error_4xx_requests": ProviderRoutingMetricsHistory.error_4xx_requests
                + stats.error_4xx_requests,
                "error_5xx_requests": ProviderRoutingMetricsHistory.error_5xx_requests
                + stats.error_5xx_requests,
                "error_429_requests": ProviderRoutingMetricsHistory.error_429_requests
                + stats.error_429_requests,
                "error_timeout_requests": ProviderRoutingMetricsHistory.error_timeout_requests
                + stats.error_timeout_requests,
                "latency_avg_ms": (existing_latency_sum + stats.latency_sum_ms)
                / cast(new_total, Float),
                "latency_p50_ms": (
                    (
                        ProviderRoutingMetricsHistory.latency_p50_ms
                        * ProviderRoutingMetricsHistory.total_requests_1m
                        + latency_p50 * total_requests
                    )
                    / cast(new_total, Float)
                ),
                "latency_p95_ms": (
                    (
                        ProviderRoutingMetricsHistory.latency_p95_ms
                        * ProviderRoutingMetricsHistory.total_requests_1m
                        + latency_p95 * total_requests
                    )
                    / cast(new_total, Float)
                ),
                "latency_p99_ms": (
                    (
                        ProviderRoutingMetricsHistory.latency_p99_ms
                        * ProviderRoutingMetricsHistory.total_requests_1m
                        + latency_p99 * total_requests
                    )
                    / cast(new_total, Float)
                ),
                "error_rate": cast(new_error, Float) / cast(new_total, Float),
                "success_qps_1m": cast(new_success, Float) / float(key.bucket_seconds),
                "status": self._status_from_error_rate(error_rate),
            },
        )


@dataclass(frozen=True)
class UserMetricsKey:
    user_id: UUID
    provider_id: str
    logical_model: str
    transport: str
    is_stream: bool
    window_start: dt.datetime
    bucket_seconds: BucketSeconds


class BufferedUserMetricsRecorder:
    """
    Similar to BufferedMetricsRecorder but dedicated to per-user aggregates.
    """

    def __init__(
        self,
        *,
        flush_interval_seconds: int,
        latency_sample_size: int,
        max_buffered_buckets: int,
        success_sample_rate: float,
    ) -> None:
        self.flush_interval_seconds = flush_interval_seconds
        self.latency_sample_size = latency_sample_size
        self.max_buffered_buckets = max_buffered_buckets
        self.success_sample_rate = max(0.0, min(1.0, success_sample_rate))

        self._buffer: dict[UserMetricsKey, MetricsStats] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._flush_thread and self._flush_thread.is_alive():
            return

        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            name="user-metrics-buffer-flusher",
            daemon=True,
        )
        self._flush_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=1.0)

    def record_sample(
        self,
        *,
        user_id: UUID,
        provider_id: str,
        logical_model: str,
        transport: str,
        is_stream: bool,
        window_start: dt.datetime,
        bucket_seconds: BucketSeconds,
        success: bool,
        latency_ms: float,
    ) -> None:
        if success and self.success_sample_rate < 1.0:
            if random.random() > self.success_sample_rate:
                return

        key = UserMetricsKey(
            user_id=user_id,
            provider_id=provider_id,
            logical_model=logical_model,
            transport=transport,
            is_stream=is_stream,
            window_start=window_start,
            bucket_seconds=bucket_seconds,
        )

        with self._lock:
            stats = self._buffer.get(key) or MetricsStats()
            stats.record(
                success=success,
                latency_ms=latency_ms,
                sample_limit=self.latency_sample_size,
                error_kind=None,
            )
            self._buffer[key] = stats

            if len(self._buffer) >= self.max_buffered_buckets:
                threading.Thread(target=self.flush, daemon=True).start()

    def flush(self) -> int:
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
            logger.exception("Failed to flush buffered user routing metrics")
        finally:
            session.close()
        return flushed

    def _drain_buffer(self) -> list[tuple[UserMetricsKey, MetricsStats]]:
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
                    logger.debug("Flushed %d buffered user metric buckets", flushed)
            except Exception:
                logger.exception("Unexpected error while flushing user metrics buffer")

    def _build_upsert_stmt(self, key: UserMetricsKey, stats: MetricsStats):
        total_requests = stats.total_requests
        success_requests = stats.success_requests
        error_requests = stats.error_requests

        latency_avg = stats.latency_avg()
        latency_p95 = stats.latency_p95()
        latency_p99 = stats.latency_p99()
        error_rate = (error_requests / total_requests) if total_requests else 0.0

        base_insert = insert(UserRoutingMetricsHistory).values(
            user_id=key.user_id,
            provider_id=key.provider_id,
            logical_model=key.logical_model,
            transport=key.transport,
            is_stream=key.is_stream,
            window_start=key.window_start,
            window_duration=key.bucket_seconds,
            total_requests=total_requests,
            success_requests=success_requests,
            error_requests=error_requests,
            latency_avg_ms=latency_avg,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            error_rate=error_rate,
        )

        new_total = UserRoutingMetricsHistory.total_requests + total_requests
        new_success = UserRoutingMetricsHistory.success_requests + success_requests
        new_error = UserRoutingMetricsHistory.error_requests + error_requests

        existing_latency_sum = (
            UserRoutingMetricsHistory.latency_avg_ms
            * UserRoutingMetricsHistory.total_requests
        )

        return base_insert.on_conflict_do_update(
            constraint="uq_user_routing_metrics_history_bucket",
            set_={
                "total_requests": new_total,
                "success_requests": new_success,
                "error_requests": new_error,
                "latency_avg_ms": (existing_latency_sum + stats.latency_sum_ms)
                / cast(new_total, Float),
                "latency_p95_ms": (
                    (
                        UserRoutingMetricsHistory.latency_p95_ms
                        * UserRoutingMetricsHistory.total_requests
                        + latency_p95 * total_requests
                    )
                    / cast(new_total, Float)
                ),
                "latency_p99_ms": (
                    (
                        UserRoutingMetricsHistory.latency_p99_ms
                        * UserRoutingMetricsHistory.total_requests
                        + latency_p99 * total_requests
                    )
                    / cast(new_total, Float)
                ),
                "error_rate": cast(new_error, Float) / cast(new_total, Float),
            },
        )


__all__ = [
    "BufferedMetricsRecorder",
    "BufferedUserMetricsRecorder",
    "MetricsKey",
    "MetricsStats",
    "UserMetricsKey",
]
