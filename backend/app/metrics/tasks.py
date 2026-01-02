from __future__ import annotations

import datetime as dt
import uuid

from celery import shared_task
from sqlalchemy import Select, delete, func, select, text
from sqlalchemy.exc import ProgrammingError

from app.celery_app import celery_app
from app.db import SessionLocal
from app.metrics.offline_recalc import OfflineMetricsRecalculator
from app.models import GatewayConfig as GatewayConfigRow
from app.models.provider_metrics_history import (
    ProviderRoutingMetricsDaily,
    ProviderRoutingMetricsHistory,
    ProviderRoutingMetricsHourly,
)
from app.settings import settings

try:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
except Exception:  # pragma: no cover
    pg_insert = None  # type: ignore[assignment]

try:
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
except Exception:  # pragma: no cover
    sqlite_insert = None  # type: ignore[assignment]


def _now_utc_minute() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(second=0, microsecond=0)


def _build_recalculator() -> OfflineMetricsRecalculator:
    return OfflineMetricsRecalculator(
        diff_threshold=settings.offline_metrics_diff_threshold,
        source_version=settings.offline_metrics_source_version,
        min_total_requests=settings.offline_metrics_min_total_requests,
    )


def _clamp_retention_days(value: int) -> int:
    return max(7, min(30, value))


def _get_effective_metrics_retention_days(session) -> int:
    try:
        row = session.execute(select(GatewayConfigRow.metrics_retention_days).limit(1)).first()
        value = int(row[0]) if row and row[0] is not None else None
        if value:
            return _clamp_retention_days(value)
    except ProgrammingError:
        # DB 尚未完成迁移（表/列缺失等），直接回退到 env 默认值。
        try:
            session.rollback()
        except Exception:
            pass
    return _clamp_retention_days(int(settings.dashboard_metrics_retention_days))


class _PgAdvisoryLock:
    def __init__(self, session, lock_id: int) -> None:
        self._session = session
        self._lock_id = int(lock_id)
        self.acquired = False

    def __enter__(self):
        if self._session.get_bind().dialect.name != "postgresql":
            return self
        row = self._session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": self._lock_id},
        ).one()
        self.acquired = bool(row[0])
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._session.get_bind().dialect.name != "postgresql":
            return False
        if self.acquired:
            self._session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": self._lock_id},
            )
        return False


def _batched_delete_before_cutoff(*, session, model, cutoff: dt.datetime) -> int:
    total_deleted = 0
    batch_size = int(settings.dashboard_metrics_cleanup_batch_size)

    while True:
        ids = [
            row[0]
            for row in session.execute(
                select(model.id)
                .where(model.window_start < cutoff)
                .order_by(model.window_start.asc())
                .limit(batch_size)
            ).all()
        ]
        if not ids:
            break
        session.execute(delete(model).where(model.id.in_(ids)))
        session.commit()
        total_deleted += len(ids)
        if len(ids) < batch_size:
            break

    return total_deleted


def _iter_days(start: dt.date, end_exclusive: dt.date):
    cur = start
    while cur < end_exclusive:
        yield cur
        cur = cur + dt.timedelta(days=1)


def _is_partitioned_history_table(session) -> bool:
    if session.get_bind().dialect.name != "postgresql":
        return False
    row = session.execute(
        text(
            "SELECT 1 "
            "FROM pg_partitioned_table "
            "WHERE partrelid = 'provider_routing_metrics_history'::regclass"
        )
    ).first()
    return bool(row)


def _ensure_history_partitions_and_drop_old(*, session, retention_days: int) -> int:
    """
    Ensure daily partitions exist for the recent+near-future window and drop old partitions.

    Returns the number of partitions created + dropped (best-effort).
    """
    if session.get_bind().dialect.name != "postgresql":
        return 0

    now = dt.datetime.now(dt.UTC)
    today = now.date()
    keep_from_day = today - dt.timedelta(days=retention_days)

    # Create partitions for [keep_from_day-2, today+2] to avoid default partition usage.
    start_day = keep_from_day - dt.timedelta(days=2)
    end_day = today + dt.timedelta(days=3)

    changed = 0

    def _part_name(day: dt.date) -> str:
        return f"provider_routing_metrics_history_p{day.strftime('%Y%m%d')}"

    for day in _iter_days(start_day, end_day):
        part = _part_name(day)
        start = dt.datetime.combine(day, dt.time(0, 0, 0), tzinfo=dt.UTC).isoformat()
        end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 0, 0), tzinfo=dt.UTC).isoformat()

        exists = session.execute(text("SELECT to_regclass(:name)"), {"name": part}).scalar_one_or_none()
        if exists is None:
            session.execute(
                text(
                    f"CREATE TABLE {part} "
                    "PARTITION OF provider_routing_metrics_history "
                    f"FOR VALUES FROM ('{start}') TO ('{end}')"
                )
            )
            changed += 1

        # Best-effort local indexes (do not rely on partitioned index attachment).
        session.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {part}_provider_logical_window "
                f"ON {part} (provider_id, logical_model, transport, is_stream, window_start)"
            )
        )
        session.execute(text(f"CREATE INDEX IF NOT EXISTS {part}_user_window ON {part} (user_id, window_start)"))
        session.execute(text(f"CREATE INDEX IF NOT EXISTS {part}_api_key_window ON {part} (api_key_id, window_start)"))

    # Ensure DEFAULT partition has basic indexes as a safety net.
    session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS provider_routing_metrics_history_default_provider_logical_window "
            "ON provider_routing_metrics_history_default (provider_id, logical_model, transport, is_stream, window_start)"
        )
    )
    session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS provider_routing_metrics_history_default_user_window "
            "ON provider_routing_metrics_history_default (user_id, window_start)"
        )
    )
    session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS provider_routing_metrics_history_default_api_key_window "
            "ON provider_routing_metrics_history_default (api_key_id, window_start)"
        )
    )

    # Drop partitions older than keep_from_day.
    parts = session.execute(
        text(
            "SELECT c.relname "
            "FROM pg_inherits i "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = 'provider_routing_metrics_history'"
        )
    ).all()
    for (relname,) in parts:
        if not isinstance(relname, str):
            continue
        if not relname.startswith("provider_routing_metrics_history_p"):
            continue
        suffix = relname.removeprefix("provider_routing_metrics_history_p")
        if len(suffix) != 8 or not suffix.isdigit():
            continue
        try:
            day = dt.datetime.strptime(suffix, "%Y%m%d").date()
        except Exception:
            continue
        if day < keep_from_day:
            session.execute(text(f"DROP TABLE IF EXISTS {relname}"))
            changed += 1

    # Clean up any rows that accidentally landed in the DEFAULT partition (batched by ctid).
    cutoff_ts = dt.datetime.combine(keep_from_day, dt.time(0, 0, 0), tzinfo=dt.UTC)
    batch_size = int(settings.dashboard_metrics_cleanup_batch_size)
    while True:
        deleted = session.execute(
            text(
                "WITH doomed AS ("
                "  SELECT ctid FROM provider_routing_metrics_history_default "
                "  WHERE window_start < :cutoff "
                "  LIMIT :batch"
                ") "
                "DELETE FROM provider_routing_metrics_history_default d "
                "USING doomed "
                "WHERE d.ctid = doomed.ctid"
            ),
            {"cutoff": cutoff_ts, "batch": batch_size},
        ).rowcount
        session.commit()
        if not deleted:
            break
    return changed


def _utc_floor_hour(ts: dt.datetime) -> dt.datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.UTC)
    return ts.replace(minute=0, second=0, microsecond=0)


def _utc_floor_day(ts: dt.datetime) -> dt.datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.UTC)
    return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def _effective_rollup_end(*, bucket: str) -> dt.datetime:
    now = _now_utc_minute() - dt.timedelta(minutes=max(settings.dashboard_metrics_rollup_guard_minutes, 0))
    if bucket == "hour":
        return _utc_floor_hour(now)
    return _utc_floor_day(now)


def _rollup_select_from_minute(
    *,
    bucket: str,
    start_at: dt.datetime,
    end_at: dt.datetime,
    source_model=ProviderRoutingMetricsHistory,
    requests_col=ProviderRoutingMetricsHistory.total_requests_1m,
) -> Select:
    """
    Build an aggregation SELECT over minute-bucket history.

    Note: percentile rollups are weighted averages (trend-oriented, not exact).
    """

    bucket_start = func.date_trunc(bucket, source_model.window_start).label("bucket_start")
    weight = func.sum(requests_col).label("weight_sum")

    return (
        select(
            bucket_start,
            source_model.provider_id,
            source_model.logical_model,
            source_model.transport,
            source_model.is_stream,
            source_model.user_id,
            source_model.api_key_id,
            func.coalesce(func.sum(requests_col), 0).label("total_requests"),
            func.coalesce(func.sum(source_model.success_requests), 0).label("success_requests"),
            func.coalesce(func.sum(source_model.error_requests), 0).label("error_requests"),
            func.coalesce(
                func.sum(source_model.latency_avg_ms * requests_col),
                0,
            ).label("lat_avg_sum"),
            func.coalesce(
                func.sum(source_model.latency_p50_ms * requests_col),
                0,
            ).label("lat_p50_sum"),
            func.coalesce(
                func.sum(source_model.latency_p95_ms * requests_col),
                0,
            ).label("lat_p95_sum"),
            func.coalesce(
                func.sum(source_model.latency_p99_ms * requests_col),
                0,
            ).label("lat_p99_sum"),
            func.coalesce(func.sum(source_model.error_4xx_requests), 0).label("error_4xx_requests"),
            func.coalesce(func.sum(source_model.error_5xx_requests), 0).label("error_5xx_requests"),
            func.coalesce(func.sum(source_model.error_429_requests), 0).label("error_429_requests"),
            func.coalesce(func.sum(source_model.error_timeout_requests), 0).label(
                "error_timeout_requests"
            ),
            func.coalesce(func.sum(source_model.input_tokens_sum), 0).label("input_tokens_sum"),
            func.coalesce(func.sum(source_model.output_tokens_sum), 0).label("output_tokens_sum"),
            func.coalesce(func.sum(source_model.total_tokens_sum), 0).label("total_tokens_sum"),
            func.coalesce(func.sum(source_model.token_estimated_requests), 0).label(
                "token_estimated_requests"
            ),
            weight,
        )
        .where(
            source_model.window_start >= start_at,
            source_model.window_start < end_at,
        )
        .group_by(
            bucket_start,
            source_model.provider_id,
            source_model.logical_model,
            source_model.transport,
            source_model.is_stream,
            source_model.user_id,
            source_model.api_key_id,
        )
    )


def _upsert_rollup_rows(
    *,
    session,
    target_model,
    uq_constraint: str,
    rows: list[dict],
) -> int:
    if not rows:
        return 0

    # Core insert executemany may not always apply Python-side defaults reliably across dialects.
    # Generate UUID primary keys explicitly to keep rollup tasks robust.
    for row in rows:
        row.setdefault("id", uuid.uuid4())

    dialect = session.get_bind().dialect.name
    if dialect == "postgresql" and pg_insert is not None:
        stmt = pg_insert(target_model).values(rows)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            constraint=uq_constraint,
            set_={
                "updated_at": func.now(),
                "window_duration": excluded.window_duration,
                "total_requests": excluded.total_requests,
                "success_requests": excluded.success_requests,
                "error_requests": excluded.error_requests,
                "latency_avg_ms": excluded.latency_avg_ms,
                "latency_p50_ms": excluded.latency_p50_ms,
                "latency_p95_ms": excluded.latency_p95_ms,
                "latency_p99_ms": excluded.latency_p99_ms,
                "error_rate": excluded.error_rate,
                "success_qps": excluded.success_qps,
                "status": excluded.status,
                "error_4xx_requests": excluded.error_4xx_requests,
                "error_5xx_requests": excluded.error_5xx_requests,
                "error_429_requests": excluded.error_429_requests,
                "error_timeout_requests": excluded.error_timeout_requests,
                "input_tokens_sum": excluded.input_tokens_sum,
                "output_tokens_sum": excluded.output_tokens_sum,
                "total_tokens_sum": excluded.total_tokens_sum,
                "token_estimated_requests": excluded.token_estimated_requests,
            },
        )
        result = session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    if dialect == "sqlite" and sqlite_insert is not None:
        stmt = sqlite_insert(target_model).values(rows)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "provider_id",
                "logical_model",
                "transport",
                "is_stream",
                "user_id",
                "api_key_id",
                "window_start",
            ],
            set_={
                "updated_at": func.now(),
                "window_duration": excluded.window_duration,
                "total_requests": excluded.total_requests,
                "success_requests": excluded.success_requests,
                "error_requests": excluded.error_requests,
                "latency_avg_ms": excluded.latency_avg_ms,
                "latency_p50_ms": excluded.latency_p50_ms,
                "latency_p95_ms": excluded.latency_p95_ms,
                "latency_p99_ms": excluded.latency_p99_ms,
                "error_rate": excluded.error_rate,
                "success_qps": excluded.success_qps,
                "status": excluded.status,
                "error_4xx_requests": excluded.error_4xx_requests,
                "error_5xx_requests": excluded.error_5xx_requests,
                "error_429_requests": excluded.error_429_requests,
                "error_timeout_requests": excluded.error_timeout_requests,
                "input_tokens_sum": excluded.input_tokens_sum,
                "output_tokens_sum": excluded.output_tokens_sum,
                "total_tokens_sum": excluded.total_tokens_sum,
                "token_estimated_requests": excluded.token_estimated_requests,
            },
        )
        result = session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    # Fallback: no-op (unsupported dialect).
    return 0


def _rollup_range(
    *,
    session,
    bucket: str,
    target_model,
    uq_constraint: str,
    window_seconds: int,
    default_lookback_days: int,
    source_model=ProviderRoutingMetricsHistory,
    requests_col=ProviderRoutingMetricsHistory.total_requests_1m,
) -> int:
    end_at = _effective_rollup_end(bucket=bucket)
    if bucket == "hour":
        lookback_start = end_at - dt.timedelta(days=default_lookback_days)
        last = session.execute(select(func.max(target_model.window_start))).scalar_one_or_none()
        start_at = _utc_floor_hour(last) + dt.timedelta(hours=1) if last else _utc_floor_hour(lookback_start)
        start_at = max(start_at, _utc_floor_hour(lookback_start))
    else:
        lookback_start = end_at - dt.timedelta(days=default_lookback_days)
        last = session.execute(select(func.max(target_model.window_start))).scalar_one_or_none()
        start_at = _utc_floor_day(last) + dt.timedelta(days=1) if last else _utc_floor_day(lookback_start)
        start_at = max(start_at, _utc_floor_day(lookback_start))

    if start_at >= end_at:
        return 0

    # Postgres: do aggregation in DB.
    if session.get_bind().dialect.name == "postgresql":
        rows = session.execute(
            _rollup_select_from_minute(
                bucket=bucket,
                start_at=start_at,
                end_at=end_at,
                source_model=source_model,
                requests_col=requests_col,
            )
        ).all()
        payloads: list[dict] = []
        for row in rows:
            weight_sum = float(row[-1] or 0)
            total_requests = int(row[7] or 0)
            success_requests = int(row[8] or 0)
            error_requests = int(row[9] or 0)
            error_rate = (error_requests / total_requests) if total_requests else 0.0
            payloads.append(
                {
                    "provider_id": row[1],
                    "logical_model": row[2],
                    "transport": row[3],
                    "is_stream": bool(row[4]),
                    "user_id": row[5],
                    "api_key_id": row[6],
                    "window_start": row[0],
                    "window_duration": window_seconds,
                    "total_requests": total_requests,
                    "success_requests": success_requests,
                    "error_requests": error_requests,
                    "latency_avg_ms": float(row[10] / weight_sum) if weight_sum else 0.0,
                    "latency_p50_ms": float(row[11] / weight_sum) if weight_sum else 0.0,
                    "latency_p95_ms": float(row[12] / weight_sum) if weight_sum else 0.0,
                    "latency_p99_ms": float(row[13] / weight_sum) if weight_sum else 0.0,
                    "error_rate": float(error_rate),
                    "success_qps": float(success_requests / window_seconds) if window_seconds else 0.0,
                    "status": "unknown",
                    "error_4xx_requests": int(row[14] or 0),
                    "error_5xx_requests": int(row[15] or 0),
                    "error_429_requests": int(row[16] or 0),
                    "error_timeout_requests": int(row[17] or 0),
                    "input_tokens_sum": int(row[18] or 0),
                    "output_tokens_sum": int(row[19] or 0),
                    "total_tokens_sum": int(row[20] or 0),
                    "token_estimated_requests": int(row[21] or 0),
                }
            )
        written = _upsert_rollup_rows(session=session, target_model=target_model, uq_constraint=uq_constraint, rows=payloads)
        session.commit()
        return written

    # Non-Postgres: Python aggregation (best-effort).
    minute_rows = session.execute(
        select(
            source_model.window_start,
            source_model.provider_id,
            source_model.logical_model,
            source_model.transport,
            source_model.is_stream,
            source_model.user_id,
            source_model.api_key_id,
            requests_col,
            source_model.success_requests,
            source_model.error_requests,
            source_model.latency_avg_ms,
            source_model.latency_p50_ms,
            source_model.latency_p95_ms,
            source_model.latency_p99_ms,
            source_model.error_4xx_requests,
            source_model.error_5xx_requests,
            source_model.error_429_requests,
            source_model.error_timeout_requests,
            source_model.input_tokens_sum,
            source_model.output_tokens_sum,
            source_model.total_tokens_sum,
            source_model.token_estimated_requests,
        ).where(
            source_model.window_start >= start_at,
            source_model.window_start < end_at,
        )
    ).all()

    buckets: dict[tuple, dict] = {}
    for r in minute_rows:
        ts = r[0]
        bucket_start = _utc_floor_hour(ts) if bucket == "hour" else _utc_floor_day(ts)
        key = (bucket_start, r[1], r[2], r[3], bool(r[4]), r[5], r[6])
        agg = buckets.get(key)
        if agg is None:
            agg = {
                "provider_id": r[1],
                "logical_model": r[2],
                "transport": r[3],
                "is_stream": bool(r[4]),
                "user_id": r[5],
                "api_key_id": r[6],
                "window_start": bucket_start,
                "window_duration": window_seconds,
                "total_requests": 0,
                "success_requests": 0,
                "error_requests": 0,
                "_weight_sum": 0.0,
                "_lat_avg_sum": 0.0,
                "_lat_p50_sum": 0.0,
                "_lat_p95_sum": 0.0,
                "_lat_p99_sum": 0.0,
                "error_4xx_requests": 0,
                "error_5xx_requests": 0,
                "error_429_requests": 0,
                "error_timeout_requests": 0,
                "input_tokens_sum": 0,
                "output_tokens_sum": 0,
                "total_tokens_sum": 0,
                "token_estimated_requests": 0,
            }
            buckets[key] = agg

        total = int(r[7] or 0)
        agg["total_requests"] += total
        agg["success_requests"] += int(r[8] or 0)
        agg["error_requests"] += int(r[9] or 0)
        agg["_weight_sum"] += float(total)
        agg["_lat_avg_sum"] += float(r[10] or 0) * total
        agg["_lat_p50_sum"] += float(r[11] or 0) * total
        agg["_lat_p95_sum"] += float(r[12] or 0) * total
        agg["_lat_p99_sum"] += float(r[13] or 0) * total
        agg["error_4xx_requests"] += int(r[14] or 0)
        agg["error_5xx_requests"] += int(r[15] or 0)
        agg["error_429_requests"] += int(r[16] or 0)
        agg["error_timeout_requests"] += int(r[17] or 0)
        agg["input_tokens_sum"] += int(r[18] or 0)
        agg["output_tokens_sum"] += int(r[19] or 0)
        agg["total_tokens_sum"] += int(r[20] or 0)
        agg["token_estimated_requests"] += int(r[21] or 0)

    payloads = []
    for agg in buckets.values():
        weight_sum = float(agg.pop("_weight_sum") or 0.0)
        lat_avg_sum = float(agg.pop("_lat_avg_sum") or 0.0)
        lat_p50_sum = float(agg.pop("_lat_p50_sum") or 0.0)
        lat_p95_sum = float(agg.pop("_lat_p95_sum") or 0.0)
        lat_p99_sum = float(agg.pop("_lat_p99_sum") or 0.0)
        total_requests = int(agg["total_requests"] or 0)
        success_requests = int(agg["success_requests"] or 0)
        error_requests = int(agg["error_requests"] or 0)
        agg["latency_avg_ms"] = (lat_avg_sum / weight_sum) if weight_sum else 0.0
        agg["latency_p50_ms"] = (lat_p50_sum / weight_sum) if weight_sum else 0.0
        agg["latency_p95_ms"] = (lat_p95_sum / weight_sum) if weight_sum else 0.0
        agg["latency_p99_ms"] = (lat_p99_sum / weight_sum) if weight_sum else 0.0
        agg["error_rate"] = (error_requests / total_requests) if total_requests else 0.0
        agg["success_qps"] = (success_requests / window_seconds) if window_seconds else 0.0
        agg["status"] = "unknown"
        payloads.append(agg)

    written = _upsert_rollup_rows(session=session, target_model=target_model, uq_constraint=uq_constraint, rows=payloads)
    session.commit()
    return written


def _cleanup_rollup(*, session, model, retention_days: int) -> int:
    cutoff = _now_utc_minute() - dt.timedelta(days=max(retention_days, 0))
    return _batched_delete_before_cutoff(session=session, model=model, cutoff=cutoff)


@shared_task(name="tasks.metrics.offline_recalc_recent")
def recalc_recent_metrics(hours: int | None = None) -> int:
    """Recompute aggregate metrics for the recent lookback window."""

    session = SessionLocal()
    try:
        with _PgAdvisoryLock(session, lock_id=8102003) as lock:
            if session.get_bind().dialect.name == "postgresql" and not lock.acquired:
                return 0

            # 计算重算区间的结束时间：为避免与最新写入强竞争，可以向历史偏移一段保护时间。
            now = _now_utc_minute()
            guard_hours = max(settings.offline_metrics_guard_hours, 0)
            end = now - dt.timedelta(hours=guard_hours) if guard_hours else now

            lookback = hours or settings.offline_metrics_lookback_hours
            if lookback <= 0:
                return 0
            start = end - dt.timedelta(hours=lookback)

            total_written = 0
            for window in settings.offline_metrics_windows:
                recalculator = _build_recalculator()
                total_written += recalculator.recalculate_and_persist(
                    session,
                    start=start,
                    end=end,
                    window_seconds=window,
                )

            session.commit()
            return total_written
    finally:
        session.close()


@shared_task(name="tasks.metrics.cleanup_history")
def cleanup_metrics_history() -> int:
    """
    清理 Dashboard 指标分钟桶历史数据，避免表无限膨胀。

    - 留存天数来自 gateway_config.metrics_retention_days（可被管理员在 UI 中调整）；
    - 若 gateway_config 尚未初始化，则回退到 settings.dashboard_metrics_retention_days。
    """

    session = SessionLocal()
    try:
        with _PgAdvisoryLock(session, lock_id=8102000) as lock:
            if session.get_bind().dialect.name == "postgresql" and not lock.acquired:
                return 0

            retention_days = _get_effective_metrics_retention_days(session)
            if _is_partitioned_history_table(session):
                return _ensure_history_partitions_and_drop_old(session=session, retention_days=retention_days)

            cutoff = _now_utc_minute() - dt.timedelta(days=retention_days)
            return _batched_delete_before_cutoff(session=session, model=ProviderRoutingMetricsHistory, cutoff=cutoff)
    finally:
        session.close()


@shared_task(name="tasks.metrics.rollup_hourly")
def rollup_metrics_hourly() -> int:
    """Roll up minute-bucket history into hourly metrics."""
    session = SessionLocal()
    try:
        with _PgAdvisoryLock(session, lock_id=8102001) as lock:
            if session.get_bind().dialect.name == "postgresql" and not lock.acquired:
                return 0
            return _rollup_range(
                session=session,
                bucket="hour",
                target_model=ProviderRoutingMetricsHourly,
                uq_constraint="uq_provider_routing_metrics_hourly_bucket",
                window_seconds=3600,
                default_lookback_days=7,
                source_model=ProviderRoutingMetricsHistory,
                requests_col=ProviderRoutingMetricsHistory.total_requests_1m,
            )
    finally:
        session.close()


@shared_task(name="tasks.metrics.rollup_daily")
def rollup_metrics_daily() -> int:
    """Roll up hourly metrics into daily metrics."""
    session = SessionLocal()
    try:
        with _PgAdvisoryLock(session, lock_id=8102002) as lock:
            if session.get_bind().dialect.name == "postgresql" and not lock.acquired:
                return 0
            return _rollup_range(
                session=session,
                bucket="day",
                target_model=ProviderRoutingMetricsDaily,
                uq_constraint="uq_provider_routing_metrics_daily_bucket",
                window_seconds=86400,
                default_lookback_days=30,
                source_model=ProviderRoutingMetricsHourly,
                requests_col=ProviderRoutingMetricsHourly.total_requests,
            )
    finally:
        session.close()


@shared_task(name="tasks.metrics.cleanup_hourly")
def cleanup_metrics_hourly() -> int:
    """Clean up hourly rollup history."""
    session = SessionLocal()
    try:
        with _PgAdvisoryLock(session, lock_id=8102003) as lock:
            if session.get_bind().dialect.name == "postgresql" and not lock.acquired:
                return 0
            return _cleanup_rollup(
                session=session,
                model=ProviderRoutingMetricsHourly,
                retention_days=settings.dashboard_metrics_hourly_retention_days,
            )
    finally:
        session.close()


@shared_task(name="tasks.metrics.cleanup_daily")
def cleanup_metrics_daily() -> int:
    """Clean up daily rollup history."""
    session = SessionLocal()
    try:
        with _PgAdvisoryLock(session, lock_id=8102004) as lock:
            if session.get_bind().dialect.name == "postgresql" and not lock.acquired:
                return 0
            return _cleanup_rollup(
                session=session,
                model=ProviderRoutingMetricsDaily,
                retention_days=settings.dashboard_metrics_daily_retention_days,
            )
    finally:
        session.close()


celery_app.conf.beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
if settings.offline_metrics_enabled:
    celery_app.conf.beat_schedule.update(
        {
            "offline-metrics-recalc": {
                "task": "tasks.metrics.offline_recalc_recent",
                "schedule": settings.offline_metrics_interval_seconds,
            }
        }
    )
if settings.dashboard_metrics_cleanup_enabled:
    celery_app.conf.beat_schedule.update(
        {
            "dashboard-metrics-cleanup": {
                "task": "tasks.metrics.cleanup_history",
                "schedule": settings.dashboard_metrics_cleanup_interval_seconds,
            }
        }
    )
if settings.dashboard_metrics_rollup_enabled:
    celery_app.conf.beat_schedule.update(
        {
            "dashboard-metrics-rollup-hourly": {
                "task": "tasks.metrics.rollup_hourly",
                "schedule": settings.dashboard_metrics_rollup_hourly_interval_seconds,
            },
            "dashboard-metrics-rollup-daily": {
                "task": "tasks.metrics.rollup_daily",
                "schedule": settings.dashboard_metrics_rollup_daily_interval_seconds,
            },
            "dashboard-metrics-rollup-hourly-cleanup": {
                "task": "tasks.metrics.cleanup_hourly",
                "schedule": settings.dashboard_metrics_cleanup_interval_seconds,
            },
            "dashboard-metrics-rollup-daily-cleanup": {
                "task": "tasks.metrics.cleanup_daily",
                "schedule": settings.dashboard_metrics_cleanup_interval_seconds,
            },
        }
    )


__all__ = [
    "cleanup_metrics_daily",
    "cleanup_metrics_history",
    "cleanup_metrics_hourly",
    "recalc_recent_metrics",
    "rollup_metrics_daily",
    "rollup_metrics_hourly",
]
