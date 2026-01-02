"""
Memory metrics API routes for system monitoring dashboard.

Provides endpoints for:
- KPI summary (trigger rate, hit rate, latency, backlog)
- Time series data (pulse)
- Active alerts based on thresholds
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.db import get_db_session
from app.models.memory_metrics_history import MemoryMetricsHistory, MemoryMetricsHourly
from app.deps import get_redis
from app.redis_client import redis_get_json, redis_set_json
from app.schemas.memory_metrics import (
    MemoryAlert,
    MemoryAlertThresholds,
    MemoryMetricsAlerts,
    MemoryMetricsDashboard,
    MemoryMetricsDataPoint,
    MemoryMetricsKpis,
    MemoryMetricsPulse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics/memory", tags=["Memory Metrics"])

CACHE_TTL_SECONDS = 60  # 1 minute cache


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _retrieval_skipped_expr(model):
    """
    Hourly rollup 表不一定包含 retrieval_skipped 字段；可由 total_requests - retrieval_triggered 推导。
    """
    if hasattr(model, "retrieval_skipped"):
        return model.retrieval_skipped
    return model.total_requests - model.retrieval_triggered


def _routing_skipped_expr(model):
    """
    Hourly rollup 表不一定包含 routing_skipped 字段；可由 routing_requests - stored_user - stored_system 推导。
    """
    if hasattr(model, "routing_skipped"):
        return model.routing_skipped
    return model.routing_requests - model.routing_stored_user - model.routing_stored_system


def _latency_sum_expr(model):
    """
    KPI/pulse 需要 latency 的分子（sum_ms）。History 表有 retrieval_latency_sum_ms；
    Hourly rollup 只有 retrieval_latency_avg_ms，因此用 avg_ms * retrieval_triggered 近似还原。
    """
    if hasattr(model, "retrieval_latency_sum_ms"):
        return model.retrieval_latency_sum_ms
    return model.retrieval_latency_avg_ms * model.retrieval_triggered


def _resolve_time_range(time_range: str) -> tuple[dt.datetime, dt.datetime]:
    """Resolve time range string to start/end datetime."""
    now = _utc_now()
    end_at = now

    if time_range == "today":
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_range == "7d":
        start_at = now - dt.timedelta(days=7)
    elif time_range == "30d":
        start_at = now - dt.timedelta(days=30)
    else:
        start_at = now - dt.timedelta(days=7)

    return start_at, end_at


def _ensure_superuser(user: AuthenticatedUser) -> None:
    """Ensure user is superuser for system-level metrics."""
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser access required")


@router.get(
    "/kpis",
    response_model=MemoryMetricsKpis,
    summary="获取记忆系统 KPI 指标",
)
async def get_memory_kpis(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> MemoryMetricsKpis:
    """Get memory system KPI summary."""
    _ensure_superuser(current_user)

    cache_key = f"metrics:memory:kpis:{time_range}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return MemoryMetricsKpis.model_validate(cached)
        except Exception:
            logger.info("memory metrics cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)

    # Choose model based on time range
    model = MemoryMetricsHistory if time_range == "today" else MemoryMetricsHourly

    stmt = select(
        func.coalesce(func.sum(model.total_requests), 0).label("total_requests"),
        func.coalesce(func.sum(model.retrieval_triggered), 0).label("retrieval_triggered"),
        func.coalesce(func.sum(_retrieval_skipped_expr(model)), 0).label("retrieval_skipped"),
        func.coalesce(func.sum(model.memory_hits), 0).label("memory_hits"),
        func.coalesce(func.sum(model.memory_misses), 0).label("memory_misses"),
        func.coalesce(func.sum(model.routing_requests), 0).label("routing_requests"),
        func.coalesce(func.sum(model.routing_stored_user), 0).label("routing_stored_user"),
        func.coalesce(func.sum(model.routing_stored_system), 0).label("routing_stored_system"),
        func.coalesce(func.sum(_routing_skipped_expr(model)), 0).label("routing_skipped"),
        func.coalesce(func.sum(model.session_count), 0).label("session_count"),
        func.coalesce(func.sum(model.backlog_batches_sum), 0).label("backlog_batches_sum"),
        func.coalesce(func.max(model.backlog_batches_max), 0).label("backlog_batches_max"),
        # Weighted average latency
        func.coalesce(func.sum(_latency_sum_expr(model)), 0).label("latency_sum"),
        # For P95, use weighted average of P95s
        func.coalesce(
            func.sum(model.retrieval_latency_p95_ms * model.retrieval_triggered) /
            func.nullif(func.sum(model.retrieval_triggered), 0),
            0
        ).label("latency_p95"),
    ).where(
        model.window_start >= start_at,
        model.window_start < end_at,
    )

    row = db.execute(stmt).one()

    total_requests = int(row.total_requests or 0)
    retrieval_triggered = int(row.retrieval_triggered or 0)
    retrieval_skipped = int(row.retrieval_skipped or 0)
    memory_hits = int(row.memory_hits or 0)
    memory_misses = int(row.memory_misses or 0)
    session_count = int(row.session_count or 0)
    backlog_batches_sum = int(row.backlog_batches_sum or 0)

    # Calculate rates
    trigger_rate = retrieval_triggered / total_requests if total_requests > 0 else 0.0
    hit_rate = memory_hits / (memory_hits + memory_misses) if (memory_hits + memory_misses) > 0 else 0.0
    avg_backlog = backlog_batches_sum / session_count if session_count > 0 else 0.0

    # Calculate average latency
    latency_sum = float(row.latency_sum or 0)
    latency_avg = latency_sum / retrieval_triggered if retrieval_triggered > 0 else 0.0

    kpis = MemoryMetricsKpis(
        time_range=time_range,
        total_requests=total_requests,
        retrieval_triggered=retrieval_triggered,
        retrieval_skipped=retrieval_skipped,
        trigger_rate=trigger_rate,
        hit_rate=hit_rate,
        retrieval_latency_avg_ms=latency_avg,
        retrieval_latency_p95_ms=float(row.latency_p95 or 0),
        memory_hits=memory_hits,
        memory_misses=memory_misses,
        routing_requests=int(row.routing_requests or 0),
        routing_stored_user=int(row.routing_stored_user or 0),
        routing_stored_system=int(row.routing_stored_system or 0),
        routing_skipped=int(row.routing_skipped or 0),
        session_count=session_count,
        avg_backlog_per_session=avg_backlog,
        backlog_batches_max=int(row.backlog_batches_max or 0),
    )

    await redis_set_json(redis, cache_key, kpis.model_dump(mode="json"), ttl_seconds=CACHE_TTL_SECONDS)
    return kpis


@router.get(
    "/pulse",
    response_model=MemoryMetricsPulse,
    summary="获取记忆系统时间序列数据",
)
async def get_memory_pulse(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    granularity: Literal["minute", "hour"] = Query("hour"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> MemoryMetricsPulse:
    """Get memory metrics time series."""
    _ensure_superuser(current_user)

    cache_key = f"metrics:memory:pulse:{time_range}:{granularity}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return MemoryMetricsPulse.model_validate(cached)
        except Exception:
            logger.info("memory metrics cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)

    # Choose model based on granularity
    model = MemoryMetricsHistory if granularity == "minute" else MemoryMetricsHourly

    stmt = select(
        model.window_start,
        func.coalesce(func.sum(model.total_requests), 0).label("total_requests"),
        func.coalesce(func.sum(model.retrieval_triggered), 0).label("retrieval_triggered"),
        func.coalesce(func.sum(model.memory_hits), 0).label("memory_hits"),
        func.coalesce(func.sum(model.memory_misses), 0).label("memory_misses"),
        func.coalesce(func.sum(model.routing_requests), 0).label("routing_requests"),
        func.coalesce(func.sum(model.session_count), 0).label("session_count"),
        func.coalesce(func.sum(model.backlog_batches_sum), 0).label("backlog_batches_sum"),
        func.coalesce(func.sum(_latency_sum_expr(model)), 0).label("latency_sum"),
    ).where(
        model.window_start >= start_at,
        model.window_start < end_at,
    ).group_by(
        model.window_start
    ).order_by(
        model.window_start
    )

    # Limit results for large time ranges
    if time_range == "30d" and granularity == "minute":
        stmt = stmt.limit(1440)  # Last 24 hours only for minute granularity

    rows = db.execute(stmt).all()

    points = []
    for row in rows:
        total_req = int(row.total_requests or 0)
        triggered = int(row.retrieval_triggered or 0)
        hits = int(row.memory_hits or 0)
        misses = int(row.memory_misses or 0)
        sessions = int(row.session_count or 0)
        backlog_sum = int(row.backlog_batches_sum or 0)
        latency_sum = float(row.latency_sum or 0)

        trigger_rate = triggered / total_req if total_req > 0 else 0.0
        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0.0
        avg_latency = latency_sum / triggered if triggered > 0 else 0.0
        avg_backlog = backlog_sum / sessions if sessions > 0 else 0.0

        points.append(MemoryMetricsDataPoint(
            window_start=row.window_start,
            total_requests=total_req,
            retrieval_triggered=triggered,
            memory_hits=hits,
            memory_misses=misses,
            trigger_rate=trigger_rate,
            hit_rate=hit_rate,
            retrieval_latency_avg_ms=avg_latency,
            routing_requests=int(row.routing_requests or 0),
            avg_backlog_per_session=avg_backlog,
        ))

    pulse = MemoryMetricsPulse(
        time_range=time_range,
        granularity=granularity,
        points=points,
    )

    await redis_set_json(redis, cache_key, pulse.model_dump(mode="json"), ttl_seconds=CACHE_TTL_SECONDS)
    return pulse


@router.get(
    "/alerts",
    response_model=MemoryMetricsAlerts,
    summary="获取记忆系统告警",
)
async def get_memory_alerts(
    time_range: Literal["today", "7d", "30d"] = Query("today"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> MemoryMetricsAlerts:
    """Get active alerts for memory metrics based on thresholds."""
    _ensure_superuser(current_user)

    # Get current KPIs
    kpis = await get_memory_kpis(time_range, current_user, db, redis)

    # Default thresholds (could be made configurable via settings)
    thresholds = MemoryAlertThresholds()

    alerts = []
    now = _utc_now()

    # Check trigger rate
    if kpis.total_requests > 100:  # Only alert if significant traffic
        if kpis.trigger_rate < thresholds.trigger_rate_low:
            alerts.append(MemoryAlert(
                alert_type="trigger_rate_low",
                severity="warning",
                current_value=kpis.trigger_rate,
                threshold=thresholds.trigger_rate_low,
                message=f"记忆检索触发率过低 ({kpis.trigger_rate:.1%})，可能丢失记忆增强机会",
                window_start=now,
            ))
        elif kpis.trigger_rate > thresholds.trigger_rate_high:
            alerts.append(MemoryAlert(
                alert_type="trigger_rate_high",
                severity="warning",
                current_value=kpis.trigger_rate,
                threshold=thresholds.trigger_rate_high,
                message=f"记忆检索触发率过高 ({kpis.trigger_rate:.1%})，可能增加延迟和成本",
                window_start=now,
            ))

    # Check hit rate
    if kpis.retrieval_triggered > 50:  # Only alert if significant retrievals
        if kpis.hit_rate < thresholds.hit_rate_low:
            alerts.append(MemoryAlert(
                alert_type="hit_rate_low",
                severity="warning" if kpis.hit_rate > 0.1 else "critical",
                current_value=kpis.hit_rate,
                threshold=thresholds.hit_rate_low,
                message=f"记忆命中率过低 ({kpis.hit_rate:.1%})，记忆库可能需要优化",
                window_start=now,
            ))

    # Check latency
    if kpis.retrieval_latency_p95_ms > thresholds.latency_p95_high_ms:
        alerts.append(MemoryAlert(
            alert_type="latency_high",
            severity="warning" if kpis.retrieval_latency_p95_ms < 1000 else "critical",
            current_value=kpis.retrieval_latency_p95_ms,
            threshold=thresholds.latency_p95_high_ms,
            message=f"记忆检索 P95 延迟过高 ({kpis.retrieval_latency_p95_ms:.0f}ms)",
            window_start=now,
        ))

    # Check backlog
    if kpis.avg_backlog_per_session > thresholds.backlog_per_session_high:
        alerts.append(MemoryAlert(
            alert_type="backlog_high",
            severity="critical",
            current_value=kpis.avg_backlog_per_session,
            threshold=thresholds.backlog_per_session_high,
            message=f"会话积压批次过高 ({kpis.avg_backlog_per_session:.1f})，可能导致成本暴涨",
            window_start=now,
        ))

    return MemoryMetricsAlerts(
        time_range=time_range,
        thresholds=thresholds,
        alerts=alerts,
    )


@router.get(
    "/dashboard",
    response_model=MemoryMetricsDashboard,
    summary="获取记忆系统监控仪表盘",
)
async def get_memory_dashboard(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> MemoryMetricsDashboard:
    """Get combined dashboard data for memory metrics."""
    _ensure_superuser(current_user)

    # Fetch all components
    kpis = await get_memory_kpis(time_range, current_user, db, redis)
    pulse = await get_memory_pulse(time_range, "hour", current_user, db, redis)
    alerts = await get_memory_alerts(time_range, current_user, db, redis)

    return MemoryMetricsDashboard(
        kpis=kpis,
        pulse=pulse,
        alerts=alerts,
    )


__all__ = ["router"]
