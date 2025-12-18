from __future__ import annotations

import datetime as dt
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.db import get_db_session
from app.deps import get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.models import (
    CreditTransaction,
    Provider,
    ProviderRoutingMetricsDaily,
    ProviderRoutingMetricsHistory,
    ProviderRoutingMetricsHourly,
)
from app.redis_client import redis_get_json, redis_set_json
from app.schemas.dashboard_v2 import (
    DashboardCostByProvider,
    DashboardCostByProviderItem,
    DashboardProviderStatus,
    DashboardProviderStatusItem,
    DashboardPulse,
    DashboardPulsePoint,
    DashboardTokenPoint,
    DashboardTokens,
    DashboardTokensTimeSeries,
    DashboardTopModel,
    DashboardTopModels,
    SystemDashboardKpis,
    UserDashboardKpis,
)

router = APIRouter(
    prefix="/metrics/v2",
    tags=["metrics"],
    dependencies=[Depends(require_jwt_token)],
)

V2_CACHE_TTL_SECONDS = 60


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _resolve_time_range(
    time_range: Literal["today", "7d", "30d"],
) -> tuple[dt.datetime, dt.datetime]:
    now = _utc_now()
    if time_range == "today":
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_at, now
    if time_range == "7d":
        return now - dt.timedelta(days=7), now
    if time_range == "30d":
        return now - dt.timedelta(days=30), now
    return now - dt.timedelta(days=7), now


def _pulse_window() -> tuple[dt.datetime, dt.datetime]:
    end_at = _utc_now()
    start_at = end_at - dt.timedelta(hours=24)
    return start_at, end_at


def _fill_time_buckets(
    *,
    start_at: dt.datetime,
    end_at: dt.datetime,
    step_seconds: int,
    points: dict[dt.datetime, DashboardPulsePoint],
) -> list[DashboardPulsePoint]:
    # Align to UTC bucket boundaries.
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=dt.timezone.utc)
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=dt.timezone.utc)

    def _floor(ts: dt.datetime) -> dt.datetime:
        epoch = int(ts.timestamp())
        bucket = epoch - (epoch % step_seconds)
        return dt.datetime.fromtimestamp(bucket, tz=dt.timezone.utc)

    cur = _floor(start_at)
    end_floor = _floor(end_at)
    out: list[DashboardPulsePoint] = []
    while cur <= end_floor:
        out.append(
            points.get(
                cur,
                DashboardPulsePoint(
                    window_start=cur,
                    total_requests=0,
                    error_4xx_requests=0,
                    error_5xx_requests=0,
                    error_429_requests=0,
                    error_timeout_requests=0,
                    latency_p50_ms=0.0,
                    latency_p95_ms=0.0,
                    latency_p99_ms=0.0,
                ),
            )
        )
        cur = cur + dt.timedelta(seconds=step_seconds)
    return out


def _weighted_latency(sum_latency: float | None, weight: float | None) -> float:
    if not sum_latency or not weight:
        return 0.0
    try:
        return float(sum_latency / weight)
    except Exception:
        return 0.0


def _kpi_stmt(
    *,
    start_at: dt.datetime,
    end_at: dt.datetime,
    model,
    requests_col,
    scope_user_id: UUID | None,
    transport: Literal["http", "sdk", "claude_cli", "all"],
    is_stream: Literal["true", "false", "all"],
) -> Select:
    stmt = select(
        func.coalesce(func.sum(requests_col), 0).label("total_requests"),
        func.coalesce(func.sum(model.error_requests), 0).label("error_requests"),
        func.sum(
            model.latency_p95_ms
            * requests_col
        ).label("lat_p95_sum"),
        func.sum(requests_col).label("weight_sum"),
        func.coalesce(func.sum(model.input_tokens_sum), 0).label("input_tokens"),
        func.coalesce(func.sum(model.output_tokens_sum), 0).label("output_tokens"),
        func.coalesce(func.sum(model.total_tokens_sum), 0).label("total_tokens"),
        func.coalesce(func.sum(model.token_estimated_requests), 0).label("estimated_requests"),
    ).where(
        model.window_start >= start_at,
        model.window_start < end_at,
    )
    return _apply_common_filters(
        stmt,
        model=model,
        scope_user_id=scope_user_id,
        transport=transport,
        is_stream=is_stream,
    )


def _pulse_stmt(
    *,
    start_at: dt.datetime,
    end_at: dt.datetime,
    scope_user_id: UUID | None,
    transport: Literal["http", "sdk", "claude_cli", "all"],
    is_stream: Literal["true", "false", "all"],
) -> Select:
    weight = func.sum(ProviderRoutingMetricsHistory.total_requests_1m).label("weight_sum")
    return (
        select(
            ProviderRoutingMetricsHistory.window_start.label("window_start"),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_requests_1m), 0).label("total_requests"),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_4xx_requests), 0).label("error_4xx"),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_5xx_requests), 0).label("error_5xx"),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_429_requests), 0).label("error_429"),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_timeout_requests), 0).label("error_timeout"),
            func.sum(
                ProviderRoutingMetricsHistory.latency_p50_ms
                * ProviderRoutingMetricsHistory.total_requests_1m
            ).label("lat_p50_sum"),
            func.sum(
                ProviderRoutingMetricsHistory.latency_p95_ms
                * ProviderRoutingMetricsHistory.total_requests_1m
            ).label("lat_p95_sum"),
            func.sum(
                ProviderRoutingMetricsHistory.latency_p99_ms
                * ProviderRoutingMetricsHistory.total_requests_1m
            ).label("lat_p99_sum"),
            weight,
        )
        .where(
            ProviderRoutingMetricsHistory.window_start >= start_at,
            ProviderRoutingMetricsHistory.window_start < end_at,
        )
        .group_by(ProviderRoutingMetricsHistory.window_start)
        .order_by(ProviderRoutingMetricsHistory.window_start.asc())
    )


def _apply_common_filters(
    stmt: Select,
    *,
    model,
    scope_user_id: UUID | None,
    transport: Literal["http", "sdk", "claude_cli", "all"],
    is_stream: Literal["true", "false", "all"],
) -> Select:
    if scope_user_id is not None:
        stmt = stmt.where(model.user_id == scope_user_id)
    if transport != "all":
        stmt = stmt.where(model.transport == transport)
    if is_stream != "all":
        stmt = stmt.where(model.is_stream == (is_stream == "true"))
    return stmt


def _resolve_rollup_model(
    time_range: Literal["today", "7d", "30d"],
):
    if time_range == "7d":
        return ProviderRoutingMetricsHourly, ProviderRoutingMetricsHourly.total_requests
    if time_range == "30d":
        return ProviderRoutingMetricsDaily, ProviderRoutingMetricsDaily.total_requests
    return ProviderRoutingMetricsHistory, ProviderRoutingMetricsHistory.total_requests_1m


def _bucket_trunc_expr(db: Session, bucket: Literal["hour", "day"], column):
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        # Emit ISO8601 with 'Z' to keep parsing consistent (Pydantic will parse it as UTC).
        fmt = "%Y-%m-%dT%H:00:00Z" if bucket == "hour" else "%Y-%m-%dT00:00:00Z"
        return func.strftime(fmt, column)
    return func.date_trunc(bucket, column)


@router.get(
    "/user-dashboard/kpis",
    response_model=UserDashboardKpis,
    summary="用户 Dashboard v2 KPI",
)
async def user_dashboard_kpis(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> UserDashboardKpis:
    cache_key = f"metrics:v2:user-dashboard:kpis:{current_user.id}:{time_range}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return UserDashboardKpis.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    model, requests_col = _resolve_rollup_model(time_range)
    row = db.execute(
        _kpi_stmt(
            start_at=start_at,
            end_at=end_at,
            model=model,
            requests_col=requests_col,
            scope_user_id=UUID(str(current_user.id)),
            transport=transport,
            is_stream=is_stream,
        )
    ).one()

    total_requests = int(row[0] or 0)
    if time_range != "today" and total_requests == 0:
        # Rollup tables may be empty before Celery 统计任务启动；回退到分钟桶聚合以保证接口可用。
        row = db.execute(
            _kpi_stmt(
                start_at=start_at,
                end_at=end_at,
                model=ProviderRoutingMetricsHistory,
                requests_col=ProviderRoutingMetricsHistory.total_requests_1m,
                scope_user_id=UUID(str(current_user.id)),
                transport=transport,
                is_stream=is_stream,
            )
        ).one()
        total_requests = int(row[0] or 0)
    error_requests = int(row[1] or 0)
    lat_p95_ms = _weighted_latency(row[2], row[3])
    error_rate = (error_requests / total_requests) if total_requests else 0.0

    tokens = DashboardTokens(
        input=int(row[4] or 0),
        output=int(row[5] or 0),
        total=int(row[6] or 0),
        estimated_requests=int(row[7] or 0),
    )

    # credits: only count final usage/stream_usage (exclude stream_estimate to avoid double count).
    credits_stmt = (
        select(
            func.coalesce(func.sum(-CreditTransaction.amount), 0).label("spent"),
        )
        .where(CreditTransaction.user_id == UUID(str(current_user.id)))
        .where(CreditTransaction.created_at >= start_at)
        .where(CreditTransaction.created_at < end_at)
        .where(CreditTransaction.amount < 0)
        .where(CreditTransaction.reason.in_(("usage", "stream_usage")))
    )
    credits_spent = int(db.execute(credits_stmt).scalar_one() or 0)

    payload = UserDashboardKpis(
        time_range=time_range,
        total_requests=total_requests,
        error_rate=float(error_rate),
        latency_p95_ms=float(lat_p95_ms),
        tokens=tokens,
        credits_spent=credits_spent,
    )
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/user-dashboard/pulse",
    response_model=DashboardPulse,
    summary="用户 Dashboard v2 近 24h 脉搏（分钟）",
)
async def user_dashboard_pulse(
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardPulse:
    cache_key = f"metrics:v2:user-dashboard:pulse:{current_user.id}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardPulse.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _pulse_window()
    stmt = _pulse_stmt(
        start_at=start_at,
        end_at=end_at,
        scope_user_id=UUID(str(current_user.id)),
        transport=transport,
        is_stream=is_stream,
    )
    stmt = _apply_common_filters(
        stmt,
        model=ProviderRoutingMetricsHistory,
        scope_user_id=UUID(str(current_user.id)),
        transport=transport,
        is_stream=is_stream,
    )
    rows = db.execute(stmt).all()

    points: dict[dt.datetime, DashboardPulsePoint] = {}
    for row in rows:
        ts = row[0]
        weight_sum = row[9] or 0
        points[ts] = DashboardPulsePoint(
            window_start=ts,
            total_requests=int(row[1] or 0),
            error_4xx_requests=int(row[2] or 0),
            error_5xx_requests=int(row[3] or 0),
            error_429_requests=int(row[4] or 0),
            error_timeout_requests=int(row[5] or 0),
            latency_p50_ms=_weighted_latency(row[6], weight_sum),
            latency_p95_ms=_weighted_latency(row[7], weight_sum),
            latency_p99_ms=_weighted_latency(row[8], weight_sum),
        )

    filled = _fill_time_buckets(start_at=start_at, end_at=end_at, step_seconds=60, points=points)
    payload = DashboardPulse(points=filled)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/user-dashboard/tokens",
    response_model=DashboardTokensTimeSeries,
    summary="用户 Dashboard v2 Token 趋势（hour/day）",
)
async def user_dashboard_tokens(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    bucket: Literal["hour", "day"] = Query("hour"),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardTokensTimeSeries:
    cache_key = f"metrics:v2:user-dashboard:tokens:{current_user.id}:{time_range}:{bucket}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardTokensTimeSeries.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    use_rollup = time_range != "today"
    if use_rollup:
        rollup_model = ProviderRoutingMetricsHourly if bucket == "hour" else ProviderRoutingMetricsDaily
        bucket_start = rollup_model.window_start.label("bucket_start")
        stmt = (
            select(
                bucket_start,
                func.coalesce(func.sum(rollup_model.input_tokens_sum), 0).label("input_tokens"),
                func.coalesce(func.sum(rollup_model.output_tokens_sum), 0).label("output_tokens"),
                func.coalesce(func.sum(rollup_model.total_tokens_sum), 0).label("total_tokens"),
                func.coalesce(func.sum(rollup_model.token_estimated_requests), 0).label("estimated_requests"),
            )
            .where(
                rollup_model.window_start >= start_at,
                rollup_model.window_start < end_at,
                rollup_model.user_id == UUID(str(current_user.id)),
            )
            .group_by(bucket_start)
            .order_by(bucket_start.asc())
        )
        stmt = _apply_common_filters(
            stmt,
            model=rollup_model,
            scope_user_id=UUID(str(current_user.id)),
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()
    else:
        trunc = _bucket_trunc_expr(db, bucket, ProviderRoutingMetricsHistory.window_start).label("bucket_start")
        stmt = (
            select(
                trunc,
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.input_tokens_sum), 0).label("input_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.output_tokens_sum), 0).label("output_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_tokens_sum), 0).label("total_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.token_estimated_requests), 0).label(
                    "estimated_requests"
                ),
            )
            .where(
                ProviderRoutingMetricsHistory.window_start >= start_at,
                ProviderRoutingMetricsHistory.window_start < end_at,
                ProviderRoutingMetricsHistory.user_id == UUID(str(current_user.id)),
            )
            .group_by(trunc)
            .order_by(trunc.asc())
        )
        stmt = _apply_common_filters(
            stmt,
            model=ProviderRoutingMetricsHistory,
            scope_user_id=UUID(str(current_user.id)),
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()

    if use_rollup and not rows:
        # Rollup 尚未产出时回退到分钟桶聚合。
        trunc = _bucket_trunc_expr(db, bucket, ProviderRoutingMetricsHistory.window_start).label("bucket_start")
        stmt = (
            select(
                trunc,
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.input_tokens_sum), 0).label("input_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.output_tokens_sum), 0).label("output_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_tokens_sum), 0).label("total_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.token_estimated_requests), 0).label(
                    "estimated_requests"
                ),
            )
            .where(
                ProviderRoutingMetricsHistory.window_start >= start_at,
                ProviderRoutingMetricsHistory.window_start < end_at,
                ProviderRoutingMetricsHistory.user_id == UUID(str(current_user.id)),
            )
            .group_by(trunc)
            .order_by(trunc.asc())
        )
        stmt = _apply_common_filters(
            stmt,
            model=ProviderRoutingMetricsHistory,
            scope_user_id=UUID(str(current_user.id)),
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()

    points = [
        DashboardTokenPoint(
            window_start=row[0],
            input_tokens=int(row[1] or 0),
            output_tokens=int(row[2] or 0),
            total_tokens=int(row[3] or 0),
            estimated_requests=int(row[4] or 0),
        )
        for row in rows
    ]
    payload = DashboardTokensTimeSeries(time_range=time_range, bucket=bucket, points=points)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/user-dashboard/top-models",
    response_model=DashboardTopModels,
    summary="用户 Dashboard v2 Top Models（按请求量）",
)
async def user_dashboard_top_models(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    limit: int = Query(10, ge=1, le=50),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardTopModels:
    cache_key = f"metrics:v2:user-dashboard:top-models:{current_user.id}:{time_range}:{limit}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardTopModels.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    use_rollup = time_range != "today"
    if use_rollup:
        model, requests_col = _resolve_rollup_model(time_range)
        stmt = (
            select(
                model.logical_model,
                func.coalesce(func.sum(requests_col), 0).label("requests"),
                func.coalesce(func.sum(model.total_tokens_sum), 0).label("tokens_total"),
            )
            .where(
                model.window_start >= start_at,
                model.window_start < end_at,
                model.user_id == UUID(str(current_user.id)),
            )
            .group_by(model.logical_model)
            .order_by(func.sum(requests_col).desc())
            .limit(limit)
        )
        stmt = _apply_common_filters(
            stmt,
            model=model,
            scope_user_id=UUID(str(current_user.id)),
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()
        if not rows:
            use_rollup = False

    if not use_rollup:
        stmt = (
            select(
                ProviderRoutingMetricsHistory.logical_model,
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_requests_1m), 0).label("requests"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_tokens_sum), 0).label("tokens_total"),
            )
            .where(
                ProviderRoutingMetricsHistory.window_start >= start_at,
                ProviderRoutingMetricsHistory.window_start < end_at,
                ProviderRoutingMetricsHistory.user_id == UUID(str(current_user.id)),
            )
            .group_by(ProviderRoutingMetricsHistory.logical_model)
            .order_by(func.sum(ProviderRoutingMetricsHistory.total_requests_1m).desc())
            .limit(limit)
        )
        stmt = _apply_common_filters(
            stmt,
            model=ProviderRoutingMetricsHistory,
            scope_user_id=UUID(str(current_user.id)),
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()

    items = [
        DashboardTopModel(model=row[0], requests=int(row[1] or 0), tokens_total=int(row[2] or 0))
        for row in rows
        if row[0]
    ]
    payload = DashboardTopModels(items=items)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/user-dashboard/cost-by-provider",
    response_model=DashboardCostByProvider,
    summary="用户 Dashboard v2 成本结构（credits by provider）",
)
async def user_dashboard_cost_by_provider(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    limit: int = Query(12, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardCostByProvider:
    cache_key = f"metrics:v2:user-dashboard:cost-by-provider:{current_user.id}:{time_range}:{limit}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardCostByProvider.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    stmt = (
        select(
            CreditTransaction.provider_id,
            func.coalesce(func.sum(-CreditTransaction.amount), 0).label("spent"),
            func.count(CreditTransaction.id).label("tx_count"),
        )
        .where(
            CreditTransaction.user_id == UUID(str(current_user.id)),
            CreditTransaction.created_at >= start_at,
            CreditTransaction.created_at < end_at,
            CreditTransaction.amount < 0,
            CreditTransaction.reason.in_(("usage", "stream_usage")),
        )
        .group_by(CreditTransaction.provider_id)
        .order_by(func.sum(-CreditTransaction.amount).desc())
        .limit(limit)
    )
    items = [
        DashboardCostByProviderItem(
            provider_id=str(row[0] or "unknown"),
            credits_spent=int(row[1] or 0),
            transactions=int(row[2] or 0),
        )
        for row in db.execute(stmt).all()
    ]
    payload = DashboardCostByProvider(items=items)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


def _ensure_superuser(user: AuthenticatedUser) -> None:
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get(
    "/system-dashboard/kpis",
    response_model=SystemDashboardKpis,
    summary="系统 Dashboard v2 KPI（管理员）",
)
async def system_dashboard_kpis(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> SystemDashboardKpis:
    _ensure_superuser(current_user)
    cache_key = f"metrics:v2:system-dashboard:kpis:{time_range}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return SystemDashboardKpis.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    model, requests_col = _resolve_rollup_model(time_range)
    row = db.execute(
        _kpi_stmt(
            start_at=start_at,
            end_at=end_at,
            model=model,
            requests_col=requests_col,
            scope_user_id=None,
            transport=transport,
            is_stream=is_stream,
        )
    ).one()

    total_requests = int(row[0] or 0)
    if time_range != "today" and total_requests == 0:
        row = db.execute(
            _kpi_stmt(
                start_at=start_at,
                end_at=end_at,
                model=ProviderRoutingMetricsHistory,
                requests_col=ProviderRoutingMetricsHistory.total_requests_1m,
                scope_user_id=None,
                transport=transport,
                is_stream=is_stream,
            )
        ).one()
        total_requests = int(row[0] or 0)
    error_requests = int(row[1] or 0)
    lat_p95_ms = _weighted_latency(row[2], row[3])
    error_rate = (error_requests / total_requests) if total_requests else 0.0

    payload = SystemDashboardKpis(
        time_range=time_range,
        total_requests=total_requests,
        error_rate=float(error_rate),
        latency_p95_ms=float(lat_p95_ms),
        tokens=DashboardTokens(
            input=int(row[4] or 0),
            output=int(row[5] or 0),
            total=int(row[6] or 0),
            estimated_requests=int(row[7] or 0),
        ),
    )
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/system-dashboard/pulse",
    response_model=DashboardPulse,
    summary="系统 Dashboard v2 近 24h 脉搏（分钟，管理员）",
)
async def system_dashboard_pulse(
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardPulse:
    _ensure_superuser(current_user)
    cache_key = f"metrics:v2:system-dashboard:pulse:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardPulse.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _pulse_window()
    stmt = _pulse_stmt(start_at=start_at, end_at=end_at, scope_user_id=None, transport=transport, is_stream=is_stream)
    stmt = _apply_common_filters(stmt, model=ProviderRoutingMetricsHistory, scope_user_id=None, transport=transport, is_stream=is_stream)
    rows = db.execute(stmt).all()

    points: dict[dt.datetime, DashboardPulsePoint] = {}
    for row in rows:
        ts = row[0]
        weight_sum = row[9] or 0
        points[ts] = DashboardPulsePoint(
            window_start=ts,
            total_requests=int(row[1] or 0),
            error_4xx_requests=int(row[2] or 0),
            error_5xx_requests=int(row[3] or 0),
            error_429_requests=int(row[4] or 0),
            error_timeout_requests=int(row[5] or 0),
            latency_p50_ms=_weighted_latency(row[6], weight_sum),
            latency_p95_ms=_weighted_latency(row[7], weight_sum),
            latency_p99_ms=_weighted_latency(row[8], weight_sum),
        )

    filled = _fill_time_buckets(start_at=start_at, end_at=end_at, step_seconds=60, points=points)
    payload = DashboardPulse(points=filled)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/system-dashboard/tokens",
    response_model=DashboardTokensTimeSeries,
    summary="系统 Dashboard v2 Token 趋势（hour/day，管理员）",
)
async def system_dashboard_tokens(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    bucket: Literal["hour", "day"] = Query("hour"),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardTokensTimeSeries:
    _ensure_superuser(current_user)
    cache_key = f"metrics:v2:system-dashboard:tokens:{time_range}:{bucket}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardTokensTimeSeries.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    use_rollup = time_range != "today"
    if use_rollup:
        rollup_model = ProviderRoutingMetricsHourly if bucket == "hour" else ProviderRoutingMetricsDaily
        bucket_start = rollup_model.window_start.label("bucket_start")
        stmt = (
            select(
                bucket_start,
                func.coalesce(func.sum(rollup_model.input_tokens_sum), 0).label("input_tokens"),
                func.coalesce(func.sum(rollup_model.output_tokens_sum), 0).label("output_tokens"),
                func.coalesce(func.sum(rollup_model.total_tokens_sum), 0).label("total_tokens"),
                func.coalesce(func.sum(rollup_model.token_estimated_requests), 0).label("estimated_requests"),
            )
            .where(
                rollup_model.window_start >= start_at,
                rollup_model.window_start < end_at,
            )
            .group_by(bucket_start)
            .order_by(bucket_start.asc())
        )
        stmt = _apply_common_filters(stmt, model=rollup_model, scope_user_id=None, transport=transport, is_stream=is_stream)
        rows = db.execute(stmt).all()
    else:
        trunc = _bucket_trunc_expr(db, bucket, ProviderRoutingMetricsHistory.window_start).label("bucket_start")
        stmt = (
            select(
                trunc,
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.input_tokens_sum), 0).label("input_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.output_tokens_sum), 0).label("output_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_tokens_sum), 0).label("total_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.token_estimated_requests), 0).label(
                    "estimated_requests"
                ),
            )
            .where(
                ProviderRoutingMetricsHistory.window_start >= start_at,
                ProviderRoutingMetricsHistory.window_start < end_at,
            )
            .group_by(trunc)
            .order_by(trunc.asc())
        )
        stmt = _apply_common_filters(
            stmt,
            model=ProviderRoutingMetricsHistory,
            scope_user_id=None,
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()

    if use_rollup and not rows:
        trunc = _bucket_trunc_expr(db, bucket, ProviderRoutingMetricsHistory.window_start).label("bucket_start")
        stmt = (
            select(
                trunc,
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.input_tokens_sum), 0).label("input_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.output_tokens_sum), 0).label("output_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_tokens_sum), 0).label("total_tokens"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.token_estimated_requests), 0).label(
                    "estimated_requests"
                ),
            )
            .where(
                ProviderRoutingMetricsHistory.window_start >= start_at,
                ProviderRoutingMetricsHistory.window_start < end_at,
            )
            .group_by(trunc)
            .order_by(trunc.asc())
        )
        stmt = _apply_common_filters(
            stmt,
            model=ProviderRoutingMetricsHistory,
            scope_user_id=None,
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()
    points = [
        DashboardTokenPoint(
            window_start=row[0],
            input_tokens=int(row[1] or 0),
            output_tokens=int(row[2] or 0),
            total_tokens=int(row[3] or 0),
            estimated_requests=int(row[4] or 0),
        )
        for row in rows
    ]
    payload = DashboardTokensTimeSeries(time_range=time_range, bucket=bucket, points=points)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/system-dashboard/top-models",
    response_model=DashboardTopModels,
    summary="系统 Dashboard v2 Top Models（按请求量，管理员）",
)
async def system_dashboard_top_models(
    time_range: Literal["today", "7d", "30d"] = Query("7d"),
    limit: int = Query(10, ge=1, le=50),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardTopModels:
    _ensure_superuser(current_user)
    cache_key = f"metrics:v2:system-dashboard:top-models:{time_range}:{limit}:{transport}:{is_stream}"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardTopModels.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    start_at, end_at = _resolve_time_range(time_range)
    use_rollup = time_range != "today"
    if use_rollup:
        model, requests_col = _resolve_rollup_model(time_range)
        stmt = (
            select(
                model.logical_model,
                func.coalesce(func.sum(requests_col), 0).label("requests"),
                func.coalesce(func.sum(model.total_tokens_sum), 0).label("tokens_total"),
            )
            .where(
                model.window_start >= start_at,
                model.window_start < end_at,
            )
            .group_by(model.logical_model)
            .order_by(func.sum(requests_col).desc())
            .limit(limit)
        )
        stmt = _apply_common_filters(stmt, model=model, scope_user_id=None, transport=transport, is_stream=is_stream)
        rows = db.execute(stmt).all()
        if not rows:
            use_rollup = False

    if not use_rollup:
        stmt = (
            select(
                ProviderRoutingMetricsHistory.logical_model,
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_requests_1m), 0).label("requests"),
                func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_tokens_sum), 0).label("tokens_total"),
            )
            .where(
                ProviderRoutingMetricsHistory.window_start >= start_at,
                ProviderRoutingMetricsHistory.window_start < end_at,
            )
            .group_by(ProviderRoutingMetricsHistory.logical_model)
            .order_by(func.sum(ProviderRoutingMetricsHistory.total_requests_1m).desc())
            .limit(limit)
        )
        stmt = _apply_common_filters(
            stmt,
            model=ProviderRoutingMetricsHistory,
            scope_user_id=None,
            transport=transport,
            is_stream=is_stream,
        )
        rows = db.execute(stmt).all()

    items = [
        DashboardTopModel(model=row[0], requests=int(row[1] or 0), tokens_total=int(row[2] or 0))
        for row in rows
        if row[0]
    ]
    payload = DashboardTopModels(items=items)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


@router.get(
    "/system-dashboard/providers",
    response_model=DashboardProviderStatus,
    summary="系统 Dashboard v2 Provider 状态（管理员）",
)
async def system_dashboard_providers(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> DashboardProviderStatus:
    _ensure_superuser(current_user)
    cache_key = "metrics:v2:system-dashboard:providers"
    cached = await redis_get_json(redis, cache_key)
    if isinstance(cached, dict):
        try:
            return DashboardProviderStatus.model_validate(cached)
        except Exception:
            logger.info("metrics v2 cache malformed (key=%s)", cache_key)

    stmt = select(
        Provider.provider_id,
        Provider.operation_status,
        Provider.status,
        Provider.audit_status,
        Provider.last_check,
    ).order_by(Provider.provider_id.asc())
    items = [
        DashboardProviderStatusItem(
            provider_id=row[0],
            operation_status=row[1],
            status=row[2],
            audit_status=row[3],
            last_check=row[4],
        )
        for row in db.execute(stmt).all()
    ]
    payload = DashboardProviderStatus(items=items)
    await redis_set_json(redis, cache_key, payload.model_dump(mode="json"), ttl_seconds=V2_CACHE_TTL_SECONDS)
    return payload


__all__ = ["router"]
