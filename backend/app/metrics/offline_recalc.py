from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import AggregateRoutingMetrics, ProviderRoutingMetricsHistory


def _align_window(ts: dt.datetime, window_seconds: int) -> dt.datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.UTC)
    epoch = int(ts.timestamp())
    start_epoch = epoch - (epoch % window_seconds)
    return dt.datetime.fromtimestamp(start_epoch, tz=dt.UTC)


def _normalize_ts(ts: dt.datetime) -> dt.datetime:
    """Normalize timestamps for key comparison.

    Some backends（如 SQLite）会返回没有 tzinfo 的 datetime，而我们在内存中通常
    使用带 UTC tzinfo 的时间。为避免 AggregationKey 在不同来源之间不相等，
    这里统一转换为 UTC-aware datetime。
    """
    if ts.tzinfo is None:
        return ts.replace(tzinfo=dt.UTC)
    return ts.astimezone(dt.UTC)


def _status_from_metrics(error_rate: float, latency_p95_ms: float) -> str:
    if error_rate >= 0.5:
        return "unhealthy"
    if error_rate >= 0.2 or latency_p95_ms >= 4000:
        return "degraded"
    return "healthy"


def _weighted_percentile(points: Sequence[tuple[float, int]], percentile: float) -> float:
    if not points:
        return 0.0
    ordered = sorted(points, key=lambda item: item[0])
    total_weight = sum(weight for _, weight in ordered)
    if total_weight == 0:
        return 0.0

    threshold = total_weight * percentile
    cumulative = 0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return float(value)
    return float(ordered[-1][0])


@dataclass(frozen=True)
class AggregationKey:
    provider_id: str
    logical_model: str
    transport: str
    is_stream: bool
    user_id: UUID | None
    api_key_id: UUID | None
    window_start: dt.datetime
    window_duration: int


@dataclass
class AggregatedMetrics:
    key: AggregationKey
    total_requests: int = 0
    success_requests: int = 0
    error_requests: int = 0
    latency_points: list[tuple[float, int]] = field(default_factory=list)

    def add_latency_point(self, value: float, weight: int) -> None:
        if weight <= 0:
            return
        self.latency_points.append((value, weight))

    def accumulate(self, row: ProviderRoutingMetricsHistory) -> None:
        self.total_requests += row.total_requests_1m
        self.success_requests += row.success_requests
        self.error_requests += row.error_requests

        base_weight = max(row.total_requests_1m - 2, 0)
        tail95_weight = 1 if row.total_requests_1m > 0 else 0
        tail99_weight = 1 if row.total_requests_1m > 1 else 0

        self.add_latency_point(row.latency_avg_ms, base_weight or row.total_requests_1m)
        self.add_latency_point(row.latency_p95_ms, tail95_weight)
        self.add_latency_point(row.latency_p99_ms, tail99_weight)

    def to_payload(self) -> dict[str, object]:
        total = max(self.total_requests, 0)
        error_rate = (self.error_requests / total) if total else 0.0
        latency_p50 = _weighted_percentile(self.latency_points, 0.5)
        latency_p90 = _weighted_percentile(self.latency_points, 0.9)
        latency_p95 = _weighted_percentile(self.latency_points, 0.95)
        latency_p99 = _weighted_percentile(self.latency_points, 0.99)

        return {
            "provider_id": self.key.provider_id,
            "logical_model": self.key.logical_model,
            "transport": self.key.transport,
            "is_stream": self.key.is_stream,
            "user_id": self.key.user_id,
            "api_key_id": self.key.api_key_id,
            "window_start": self.key.window_start,
            "window_duration": self.key.window_duration,
            "total_requests": total,
            "success_requests": self.success_requests,
            "error_requests": self.error_requests,
            "latency_p50_ms": latency_p50,
            "latency_p90_ms": latency_p90,
            "latency_p95_ms": latency_p95,
            "latency_p99_ms": latency_p99,
            "error_rate": error_rate,
            "success_qps": self.success_requests / self.key.window_duration,
            "status": _status_from_metrics(error_rate, latency_p95),
        }


class OfflineMetricsRecalculator:
    """Recompute aggregate metrics from minute buckets and persist to DB."""

    def __init__(
        self,
        *,
        diff_threshold: float,
        source_version: str,
        min_total_requests: int = 1,
    ) -> None:
        self.diff_threshold = diff_threshold
        self.source_version = source_version
        self.min_total_requests = min_total_requests

    def recalculate_and_persist(
        self,
        session: Session,
        *,
        start: dt.datetime,
        end: dt.datetime,
        window_seconds: int,
        transport: str | None = None,
        is_stream: bool | None = None,
    ) -> int:
        # 关键修正：按窗口粒度向下对齐 start。
        # 否则当 start 落在窗口中间时（例如 06:11），minute 桶会被聚合到 06:00 的 window_start，
        # 但 _load_existing() 用原始 start（06:11）查询会漏掉已存在的 06:00 记录，
        # 进而在 flush 时触发 uq_aggregate_metrics_bucket 的重复插入错误。
        start = _align_window(start, window_seconds)

        payloads = self.recalculate(
            session,
            start=start,
            end=end,
            window_seconds=window_seconds,
            transport=transport,
            is_stream=is_stream,
        )
        if not payloads:
            return 0

        existing = self._load_existing(session, start, end, window_seconds)

        # 为兼容不同数据库方言，这里不依赖 INSERT .. ON CONFLICT 语法，
        # 而是按窗口键在内存中做 upsert，再用 ORM 更新/插入。
        written = 0
        now = dt.datetime.now(dt.UTC)

        for payload in payloads:
            key = self._key_from_payload(payload)
            current = existing.get(key)

            if current is None:
                # 新 bucket，直接插入
                row = AggregateRoutingMetrics(
                    provider_id=payload["provider_id"],
                    logical_model=payload["logical_model"],
                    transport=payload["transport"],
                    is_stream=payload["is_stream"],
                    user_id=payload["user_id"],
                    api_key_id=payload["api_key_id"],
                    window_start=payload["window_start"],
                    window_duration=payload["window_duration"],
                    total_requests=payload["total_requests"],
                    success_requests=payload["success_requests"],
                    error_requests=payload["error_requests"],
                    latency_p50_ms=payload["latency_p50_ms"],
                    latency_p90_ms=payload["latency_p90_ms"],
                    latency_p95_ms=payload["latency_p95_ms"],
                    latency_p99_ms=payload["latency_p99_ms"],
                    error_rate=payload["error_rate"],
                    success_qps=payload["success_qps"],
                    status=payload["status"],
                    recalculated_at=now,
                    source_version=self.source_version,
                )
                session.add(row)
                written += 1
                # 维护 existing 缓存，避免同一批次内重复插入。
                existing[key] = row
                continue

            # 已存在记录，根据差异阈值判断是否需要更新。
            if not self._should_update(current, payload):
                continue

            current.total_requests = int(payload["total_requests"])
            current.success_requests = int(payload["success_requests"])
            current.error_requests = int(payload["error_requests"])
            current.latency_p50_ms = float(payload["latency_p50_ms"])
            current.latency_p90_ms = float(payload["latency_p90_ms"])
            current.latency_p95_ms = float(payload["latency_p95_ms"])
            current.latency_p99_ms = float(payload["latency_p99_ms"])
            current.error_rate = float(payload["error_rate"])
            current.success_qps = float(payload["success_qps"])
            current.status = str(payload["status"])
            current.window_duration = int(payload["window_duration"])
            current.recalculated_at = now
            current.source_version = self.source_version

            written += 1

        session.flush()
        return written

    def recalculate(
        self,
        session: Session,
        *,
        start: dt.datetime,
        end: dt.datetime,
        window_seconds: int,
        transport: str | None = None,
        is_stream: bool | None = None,
    ) -> list[dict[str, object]]:
        rows = self._load_history(
            session,
            start=start,
            end=end,
            transport=transport,
            is_stream=is_stream,
        )
        if not rows:
            return []

        grouped: dict[AggregationKey, AggregatedMetrics] = {}
        for row in rows:
            aligned = _align_window(row.window_start, window_seconds)
            key = AggregationKey(
                provider_id=row.provider_id,
                logical_model=row.logical_model,
                transport=row.transport,
                is_stream=row.is_stream,
                user_id=row.user_id,
                api_key_id=row.api_key_id,
                window_start=aligned,
                window_duration=window_seconds,
            )
            bucket = grouped.get(key)
            if bucket is None:
                bucket = AggregatedMetrics(key)
                grouped[key] = bucket
            bucket.accumulate(row)

        return [
            bucket.to_payload()
            for bucket in grouped.values()
            if bucket.total_requests >= self.min_total_requests
        ]

    def _load_history(
        self,
        session: Session,
        *,
        start: dt.datetime,
        end: dt.datetime,
        transport: str | None,
        is_stream: bool | None,
    ) -> list[ProviderRoutingMetricsHistory]:
        stmt: Select[tuple[ProviderRoutingMetricsHistory]] = (
            select(ProviderRoutingMetricsHistory)
            .where(ProviderRoutingMetricsHistory.window_start >= start)
            .where(ProviderRoutingMetricsHistory.window_start < end)
        )

        if transport:
            stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)
        if is_stream is not None:
            stmt = stmt.where(ProviderRoutingMetricsHistory.is_stream == is_stream)

        return list(session.scalars(stmt))

    def _load_existing(
        self,
        session: Session,
        start: dt.datetime,
        end: dt.datetime,
        window_seconds: int,
    ) -> dict[AggregationKey, AggregateRoutingMetrics]:
        stmt: Select[tuple[AggregateRoutingMetrics]] = (
            select(AggregateRoutingMetrics)
            .where(AggregateRoutingMetrics.window_start >= start)
            .where(AggregateRoutingMetrics.window_start < end)
            .where(AggregateRoutingMetrics.window_duration == window_seconds)
        )
        rows = session.scalars(stmt).all()
        return {self._key_from_existing(row): row for row in rows}

    def _key_from_existing(self, row: AggregateRoutingMetrics) -> AggregationKey:
        return AggregationKey(
            provider_id=row.provider_id,
            logical_model=row.logical_model,
            transport=row.transport,
            is_stream=row.is_stream,
            user_id=row.user_id,
            api_key_id=row.api_key_id,
            window_start=_normalize_ts(row.window_start),
            window_duration=row.window_duration,
        )

    def _key_from_payload(self, payload: Mapping[str, object]) -> AggregationKey:
        return AggregationKey(
            provider_id=payload["provider_id"],
            logical_model=payload["logical_model"],
            transport=payload["transport"],
            is_stream=payload["is_stream"],
            user_id=payload["user_id"],
            api_key_id=payload["api_key_id"],
            window_start=_normalize_ts(payload["window_start"]),
            window_duration=payload["window_duration"],
        )

    def _should_update(
        self,
        existing: AggregateRoutingMetrics | None,
        payload: Mapping[str, object],
    ) -> bool:
        if existing is None:
            return True

        if existing.total_requests != payload["total_requests"]:
            return True
        if existing.success_requests != payload["success_requests"]:
            return True
        if existing.error_requests != payload["error_requests"]:
            return True

        def _relative_diff(old: float, new: float) -> float:
            if old == 0:
                return float("inf") if new else 0.0
            return abs(new - old) / abs(old)

        numeric_fields = (
            "latency_p50_ms",
            "latency_p90_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "error_rate",
        )
        for field in numeric_fields:
            old_val = getattr(existing, field)
            new_val = float(payload[field])
            if _relative_diff(old_val, new_val) >= self.diff_threshold:
                return True

        return False


__all__ = ["OfflineMetricsRecalculator"]
