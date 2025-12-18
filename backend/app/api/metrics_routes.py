from __future__ import annotations

import datetime as dt
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.db import get_db_session
from app.deps import get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.models import (
    ProviderRoutingMetricsHistory,
    UserAppRequestMetricsHistory,
    UserRoutingMetricsHistory,
)
from app.redis_client import redis_get_json, redis_set_json
from app.schemas.metrics import (
    APIKeyMetricsSummary,
    ActiveProviderMetrics,
    MetricsBucket,
    MetricsDataPoint,
    MetricsTimeRange,
    OverviewActiveProviders,
    OverviewMetricsSummary,
    OverviewMetricsTimeSeries,
    ProviderMetricsSummary,
    ProviderMetricsTimeSeries,
    UserAppUsageMetrics,
    UserMetricsSummary,
    UserActiveProviderMetrics,
    UserOverviewAppUsage,
    UserOverviewActiveProviders,
    UserOverviewMetricsSummary,
    UserOverviewMetricsTimeSeries,
)

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_jwt_token)],
)


# 概览缓存 TTL，单位秒。仪表盘类指标允许轻微延迟。
OVERVIEW_CACHE_TTL_SECONDS = 60


def _resolve_time_range(
    time_range: Literal["today", "7d", "30d", "all"],
) -> dt.datetime | None:
    now = dt.datetime.now(dt.timezone.utc)

    if time_range == MetricsTimeRange.ALL:
        return None
    if time_range == MetricsTimeRange.TODAY:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == MetricsTimeRange.LAST_7D:
        return now - dt.timedelta(days=7)
    if time_range == MetricsTimeRange.LAST_30D:
        return now - dt.timedelta(days=30)
    return None


def _build_overview_stmt(
    *,
    start_at: dt.datetime | None,
    end_at: dt.datetime | None,
    transport: Literal["http", "sdk", "claude_cli", "all"],
    is_stream: Literal["true", "false", "all"],
):
    """
    构造仪表盘概览使用的聚合查询：
    - 汇总总请求 / 成功 / 失败；
    - 统计活跃 Provider 数量。
    """
    stmt = select(
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.total_requests_1m),
            0,
        ).label("total_requests"),
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.success_requests),
            0,
        ).label("success_requests"),
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.error_requests),
            0,
        ).label("error_requests"),
        func.count(
            func.distinct(ProviderRoutingMetricsHistory.provider_id)
        ).label("active_providers"),
    )

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)
    if end_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start < end_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    return stmt


def _build_user_overview_stmt(
    *,
    user_id: UUID,
    start_at: dt.datetime | None,
    end_at: dt.datetime | None,
    transport: Literal["http", "sdk", "claude_cli", "all"],
    is_stream: Literal["true", "false", "all"],
):
    stmt = select(
        func.coalesce(func.sum(UserRoutingMetricsHistory.total_requests), 0).label("total_requests"),
        func.coalesce(func.sum(UserRoutingMetricsHistory.success_requests), 0).label("success_requests"),
        func.coalesce(func.sum(UserRoutingMetricsHistory.error_requests), 0).label("error_requests"),
        func.count(func.distinct(UserRoutingMetricsHistory.provider_id)).label("active_providers"),
    ).where(UserRoutingMetricsHistory.user_id == user_id)

    if start_at is not None:
        stmt = stmt.where(UserRoutingMetricsHistory.window_start >= start_at)
    if end_at is not None:
        stmt = stmt.where(UserRoutingMetricsHistory.window_start < end_at)

    if transport != "all":
        stmt = stmt.where(UserRoutingMetricsHistory.transport == transport)
    if is_stream != "all":
        stmt = stmt.where(
            UserRoutingMetricsHistory.is_stream == (is_stream == "true")
        )
    return stmt


def _compute_overview_windows(
    time_range: Literal["today", "7d", "30d", "all"],
) -> tuple[tuple[dt.datetime | None, dt.datetime | None], tuple[dt.datetime, dt.datetime] | None]:
    """
    计算当前周期与上一对比周期的时间窗口。

    - today/7d/30d：使用“当前时间 - 起始时间”的跨度作为窗口长度；
    - all：仅返回当前窗口（全量），上一周期为 None。
    """
    now = dt.datetime.now(dt.timezone.utc)
    start_at = _resolve_time_range(time_range)

    if start_at is None:
        # all: 不限定时间范围，不计算上一周期。
        return (None, None), None

    window = now - start_at
    if window.total_seconds() <= 0:
        # 非常规情况（例如时间被手动篡改），仅使用当前窗口。
        return (start_at, now), None

    current_range = (start_at, now)
    prev_start = start_at - window
    prev_end = start_at
    prev_range = (prev_start, prev_end)
    return current_range, prev_range


@router.get(
    "/providers/timeseries",
    response_model=ProviderMetricsTimeSeries,
    summary="获取指定 Provider + 逻辑模型的指标时间序列",
)
def get_provider_timeseries(
    provider_id: str = Query(..., description="厂商 ID，例如 openai"),
    logical_model: str = Query(..., description="逻辑模型 ID，例如 gpt-4"),
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    bucket: Literal["minute"] = Query(
        "minute",
        description="时间粒度，目前仅支持 minute（按分钟聚合）",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    db: Session = Depends(get_db_session),
) -> ProviderMetricsTimeSeries:
    """
    返回指定 provider + logical_model 在给定时间范围内的分钟级指标时间序列。
    """
    if bucket != MetricsBucket.MINUTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 bucket=minute",
        )

    start_at = _resolve_time_range(time_range)

    stmt: Select = (
        select(
            ProviderRoutingMetricsHistory.window_start,
            ProviderRoutingMetricsHistory.total_requests_1m,
            ProviderRoutingMetricsHistory.success_requests,
            ProviderRoutingMetricsHistory.error_requests,
            ProviderRoutingMetricsHistory.latency_avg_ms,
            ProviderRoutingMetricsHistory.latency_p95_ms,
            ProviderRoutingMetricsHistory.latency_p99_ms,
            ProviderRoutingMetricsHistory.error_rate,
        )
        .where(
            ProviderRoutingMetricsHistory.provider_id == provider_id,
            ProviderRoutingMetricsHistory.logical_model == logical_model,
        )
        .order_by(ProviderRoutingMetricsHistory.window_start.asc())
    )

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    try:
        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to load metrics timeseries for provider=%s logical_model=%s",
            provider_id,
            logical_model,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load metrics timeseries",
        )

    points = [
        MetricsDataPoint(
            window_start=row[0],
            total_requests=row[1],
            success_requests=row[2],
            error_requests=row[3],
            latency_avg_ms=row[4],
            latency_p95_ms=row[5],
            latency_p99_ms=row[6],
            error_rate=row[7],
        )
        for row in rows
    ]

    return ProviderMetricsTimeSeries(
        provider_id=provider_id,
        logical_model=logical_model,
        time_range=time_range,
        bucket=bucket,
        transport=transport,
        is_stream=is_stream,
        points=points,
    )


@router.get(
    "/overview/summary",
    response_model=OverviewMetricsSummary,
    summary="仪表盘概览：全局请求量 / 成功率 / 活跃 Provider 汇总",
)
async def get_overview_summary(
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> OverviewMetricsSummary:
    """
    返回仪表盘概览所需的全局聚合指标：

    - total_requests / success_requests / error_requests；
    - success_rate；
    - active_providers（当前时间范围内有流量的 Provider 数量）；
    - 以及上一对比周期的同类指标，用于前端计算环比变化。
    """
    cache_key = f"metrics:overview:summary:{time_range}:{transport}:{is_stream}"

    # 尝试从 Redis 读取缓存（缓存 miss 或 Redis 异常时回退到 DB 查询）
    if redis is not object:  # pragma: no branch - 类型占位时直接跳过
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to load metrics overview summary from Redis (key=%s)",
                cache_key,
            )
            cached = None

        if cached:
            try:
                return OverviewMetricsSummary.model_validate(cached)
            except Exception:  # pragma: no cover - 防御性日志
                logger.exception(
                    "Cached metrics overview summary is malformed, ignoring (key=%s)",
                    cache_key,
                )

    current_range, prev_range = _compute_overview_windows(time_range)

    def _load_window(
        window: tuple[dt.datetime | None, dt.datetime | None] | None,
    ) -> tuple[int, int, int, int]:
        if window is None:
            return 0, 0, 0, 0

        start_at, end_at = window
        stmt = _build_overview_stmt(
            start_at=start_at,
            end_at=end_at,
            transport=transport,
            is_stream=is_stream,
        )
        row = db.execute(stmt).one()

        total_requests = int(row.total_requests or 0)
        success_requests = int(row.success_requests or 0)
        error_requests = int(row.error_requests or 0)
        active_providers = int(row.active_providers or 0)
        return total_requests, success_requests, error_requests, active_providers

    try:
        (
            total_requests,
            success_requests,
            error_requests,
            active_providers,
        ) = _load_window(current_range)
        if prev_range is not None:
            (
                total_requests_prev,
                success_requests_prev,
                error_requests_prev,
                active_providers_prev,
            ) = _load_window(prev_range)
        else:
            total_requests_prev = None
            success_requests_prev = None
            error_requests_prev = None
            active_providers_prev = None
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception("Failed to load metrics overview summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load metrics overview summary",
        )

    if total_requests > 0:
        success_rate = success_requests / total_requests
    else:
        success_rate = 0.0

    if total_requests_prev and total_requests_prev > 0:
        success_rate_prev: float | None = success_requests_prev / total_requests_prev  # type: ignore[operator]
    else:
        success_rate_prev = None

    overview = OverviewMetricsSummary(
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        total_requests=total_requests,
        success_requests=success_requests,
        error_requests=error_requests,
        success_rate=success_rate,
        total_requests_prev=total_requests_prev,
        success_requests_prev=success_requests_prev,
        error_requests_prev=error_requests_prev,
        success_rate_prev=success_rate_prev,
        active_providers=active_providers,
        active_providers_prev=active_providers_prev,
    )

    # 将结果写入 Redis 缓存，但不影响主流程。
    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                overview.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to store metrics overview summary to Redis (key=%s)",
                cache_key,
            )

    return overview


@router.get(
    "/user-overview/timeseries",
    response_model=UserOverviewMetricsTimeSeries,
    summary="仪表盘概览（用户维度）：近期活动时间序列",
)
async def get_user_overview_timeseries(
    time_range: Literal["today", "7d", "30d", "all"] = Query("7d"),
    bucket: Literal["minute"] = Query("minute"),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> UserOverviewMetricsTimeSeries:
    if bucket != MetricsBucket.MINUTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 bucket=minute",
        )

    user_uuid = UUID(current_user.id)
    cache_key = f"metrics:user-overview:timeseries:{current_user.id}:{time_range}:{transport}:{is_stream}:{bucket}"

    if redis is not object:  # pragma: no branch
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to load user overview timeseries cache (key=%s)",
                cache_key,
            )
            cached = None
        if cached:
            try:
                return UserOverviewMetricsTimeSeries.model_validate(cached)
            except Exception:  # pragma: no cover
                logger.exception(
                    "Malformed user overview timeseries cache (key=%s)",
                    cache_key,
                )

    start_at = _resolve_time_range(time_range)

    stmt = (
        select(
            UserRoutingMetricsHistory.window_start,
            func.coalesce(func.sum(UserRoutingMetricsHistory.total_requests), 0),
            func.coalesce(func.sum(UserRoutingMetricsHistory.success_requests), 0),
            func.coalesce(func.sum(UserRoutingMetricsHistory.error_requests), 0),
            func.sum(
                UserRoutingMetricsHistory.latency_avg_ms * UserRoutingMetricsHistory.total_requests
            ).label("lat_sum"),
            func.sum(UserRoutingMetricsHistory.total_requests).label("weight_sum"),
            func.sum(
                UserRoutingMetricsHistory.latency_p95_ms * UserRoutingMetricsHistory.total_requests
            ).label("lat_p95_sum"),
            func.sum(
                UserRoutingMetricsHistory.latency_p99_ms * UserRoutingMetricsHistory.total_requests
            ).label("lat_p99_sum"),
        )
        .where(UserRoutingMetricsHistory.user_id == user_uuid)
        .group_by(UserRoutingMetricsHistory.window_start)
    )

    if start_at is not None:
        stmt = stmt.where(UserRoutingMetricsHistory.window_start >= start_at)
    if transport != "all":
        stmt = stmt.where(UserRoutingMetricsHistory.transport == transport)
    if is_stream != "all":
        stmt = stmt.where(
            UserRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    stmt = stmt.order_by(UserRoutingMetricsHistory.window_start.asc())

    try:
        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover
        logger.exception("Failed to load user overview timeseries")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user overview timeseries",
        )

    points: list[MetricsDataPoint] = []
    for row in rows:
        window_start = row[0]
        total_requests = int(row[1] or 0)
        success_requests = int(row[2] or 0)
        error_requests = int(row[3] or 0)
        lat_sum = row.lat_sum
        weight_sum = row.weight_sum or 0
        lat_p95_sum = row.lat_p95_sum
        lat_p99_sum = row.lat_p99_sum

        if total_requests > 0 and weight_sum:
            latency_avg_ms = float(lat_sum / weight_sum) if lat_sum is not None else 0.0
            latency_p95_ms = (
                float(lat_p95_sum / weight_sum) if lat_p95_sum is not None else latency_avg_ms
            )
            latency_p99_ms = (
                float(lat_p99_sum / weight_sum) if lat_p99_sum is not None else latency_p95_ms
            )
            error_rate = error_requests / total_requests
        else:
            latency_avg_ms = 0.0
            latency_p95_ms = 0.0
            latency_p99_ms = 0.0
            error_rate = 0.0

        points.append(
            MetricsDataPoint(
                window_start=window_start,
                total_requests=total_requests,
                success_requests=success_requests,
                error_requests=error_requests,
                latency_avg_ms=latency_avg_ms,
                latency_p95_ms=latency_p95_ms,
                latency_p99_ms=latency_p99_ms,
                error_rate=error_rate,
            )
        )

    result = UserOverviewMetricsTimeSeries(
        user_id=current_user.id,
        time_range=time_range,
        bucket=bucket,
        transport=transport,
        is_stream=is_stream,
        points=points,
    )

    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                result.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to store user overview timeseries cache (key=%s)",
                cache_key,
            )

    return result


@router.get(
    "/user-overview/providers",
    response_model=UserOverviewActiveProviders,
    summary="仪表盘概览（用户维度）：活跃 Provider 排行",
)
async def get_user_overview_providers(
    time_range: Literal["today", "7d", "30d", "all"] = Query("7d"),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    limit: int = Query(4, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> UserOverviewActiveProviders:
    user_uuid = UUID(current_user.id)
    cache_key = f"metrics:user-overview:providers:{current_user.id}:{time_range}:{transport}:{is_stream}:{limit}"

    if redis is not object:  # pragma: no branch
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to load user overview providers cache (key=%s)",
                cache_key,
            )
            cached = None
        if cached:
            try:
                return UserOverviewActiveProviders.model_validate(cached)
            except Exception:  # pragma: no cover
                logger.exception(
                    "Malformed user overview providers cache (key=%s)",
                    cache_key,
                )

    start_at = _resolve_time_range(time_range)

    stmt = (
        select(
            UserRoutingMetricsHistory.provider_id,
            func.coalesce(func.sum(UserRoutingMetricsHistory.total_requests), 0).label("total_requests"),
            func.coalesce(func.sum(UserRoutingMetricsHistory.success_requests), 0).label("success_requests"),
            func.coalesce(func.sum(UserRoutingMetricsHistory.error_requests), 0).label("error_requests"),
            func.sum(
                UserRoutingMetricsHistory.latency_p95_ms * UserRoutingMetricsHistory.total_requests
            ).label("latency_p95_sum"),
            func.sum(UserRoutingMetricsHistory.total_requests).label("weight_sum"),
        )
        .where(UserRoutingMetricsHistory.user_id == user_uuid)
        .group_by(UserRoutingMetricsHistory.provider_id)
    )

    if start_at is not None:
        stmt = stmt.where(UserRoutingMetricsHistory.window_start >= start_at)
    if transport != "all":
        stmt = stmt.where(UserRoutingMetricsHistory.transport == transport)
    if is_stream != "all":
        stmt = stmt.where(
            UserRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    stmt = stmt.order_by(
        func.sum(UserRoutingMetricsHistory.total_requests).desc()
    ).limit(limit)

    try:
        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover
        logger.exception("Failed to load user overview providers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user overview providers",
        )

    items: list[UserActiveProviderMetrics] = []
    for row in rows:
        provider_id = row[0]
        total_requests = int(row.total_requests or 0)
        success_requests = int(row.success_requests or 0)
        error_requests = int(row.error_requests or 0)
        latency_p95_sum = row.latency_p95_sum
        weight_sum = row.weight_sum or 0

        if weight_sum and latency_p95_sum is not None:
            latency_p95_ms: float | None = float(latency_p95_sum / weight_sum)
        else:
            latency_p95_ms = None

        success_rate = success_requests / total_requests if total_requests > 0 else 0.0

        items.append(
            UserActiveProviderMetrics(
                provider_id=provider_id,
                total_requests=total_requests,
                success_requests=success_requests,
                error_requests=error_requests,
                success_rate=success_rate,
                latency_p95_ms=latency_p95_ms,
            )
        )

    overview = UserOverviewActiveProviders(
        user_id=current_user.id,
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        items=items,
    )

    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                overview.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to store user overview providers cache (key=%s)",
                cache_key,
            )

    return overview


@router.get(
    "/user-overview/apps",
    response_model=UserOverviewAppUsage,
    summary="仪表盘概览（用户维度）：App 使用排行",
)
async def get_user_overview_apps(
    time_range: Literal["today", "7d", "30d", "all"] = Query("7d"),
    limit: int = Query(10, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> UserOverviewAppUsage:
    user_uuid = UUID(current_user.id)
    cache_key = f"metrics:user-overview:apps:{current_user.id}:{time_range}:{limit}"

    if redis is not object:  # pragma: no branch
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to load user overview apps cache (key=%s)",
                cache_key,
            )
            cached = None
        if cached:
            try:
                return UserOverviewAppUsage.model_validate(cached)
            except Exception:  # pragma: no cover
                logger.exception(
                    "Malformed user overview apps cache (key=%s)",
                    cache_key,
                )

    start_at = _resolve_time_range(time_range)

    stmt: Select = (
        select(
            UserAppRequestMetricsHistory.app_name,
            func.coalesce(func.sum(UserAppRequestMetricsHistory.total_requests), 0).label(
                "total_requests"
            ),
            func.max(UserAppRequestMetricsHistory.window_start).label("last_seen_at"),
        )
        .where(UserAppRequestMetricsHistory.user_id == user_uuid)
        .group_by(UserAppRequestMetricsHistory.app_name)
        .order_by(func.sum(UserAppRequestMetricsHistory.total_requests).desc())
        .limit(limit)
    )
    if start_at is not None:
        stmt = stmt.where(UserAppRequestMetricsHistory.window_start >= start_at)

    try:
        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover
        logger.exception("Failed to load user overview apps")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user overview apps",
        )

    items = [
        UserAppUsageMetrics(
            app_name=row[0],
            total_requests=int(row.total_requests or 0),
            last_seen_at=row.last_seen_at,
        )
        for row in rows
    ]

    result = UserOverviewAppUsage(
        user_id=current_user.id,
        time_range=time_range,
        items=items,
    )

    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                result.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to store user overview apps cache (key=%s)",
                cache_key,
            )

    return result


@router.get(
    "/overview/providers",
    response_model=OverviewActiveProviders,
    summary="仪表盘概览：活跃 Provider 列表（按请求量排序）",
)
async def get_overview_active_providers(
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    limit: int = Query(
        4,
        ge=1,
        le=50,
        description="返回的 Provider 最大数量，按请求量降序排列",
    ),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> OverviewActiveProviders:
    """
    返回在指定时间范围内有请求的 Provider 列表，用于“活跃提供商”卡片。

    - 按总请求数降序排序；
    - 延迟使用 P95 的加权平均近似；
    - 成功率 = success_requests / total_requests。
    """
    cache_key = f"metrics:overview:providers:{time_range}:{transport}:{is_stream}:{limit}"

    if redis is not object:  # pragma: no branch
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to load metrics overview providers from Redis (key=%s)",
                cache_key,
            )
            cached = None
        if cached:
            try:
                return OverviewActiveProviders.model_validate(cached)
            except Exception:  # pragma: no cover - 防御性日志
                logger.exception(
                    "Cached metrics overview providers is malformed, ignoring (key=%s)",
                    cache_key,
                )

    start_at = _resolve_time_range(time_range)

    stmt = select(
        ProviderRoutingMetricsHistory.provider_id,
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.total_requests_1m),
            0,
        ).label("total_requests"),
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.success_requests),
            0,
        ).label("success_requests"),
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.error_requests),
            0,
        ).label("error_requests"),
        func.sum(
            ProviderRoutingMetricsHistory.latency_p95_ms
            * ProviderRoutingMetricsHistory.total_requests_1m
        ).label("latency_p95_sum"),
        func.sum(ProviderRoutingMetricsHistory.total_requests_1m).label(
            "weight_sum"
        ),
    ).group_by(ProviderRoutingMetricsHistory.provider_id)

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    # 按请求量降序排列，取前 N 个。
    stmt = stmt.order_by(
        func.sum(ProviderRoutingMetricsHistory.total_requests_1m).desc()
    ).limit(limit)

    try:
        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception("Failed to load metrics overview providers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load metrics overview providers",
        )

    items: list[ActiveProviderMetrics] = []
    for row in rows:
        provider_id = row[0]
        total_requests = int(row.total_requests or 0)
        success_requests = int(row.success_requests or 0)
        error_requests = int(row.error_requests or 0)
        latency_p95_sum = row.latency_p95_sum
        weight_sum = row.weight_sum or 0

        if weight_sum and latency_p95_sum is not None:
            latency_p95_ms: float | None = float(latency_p95_sum / weight_sum)
        else:
            latency_p95_ms = None

        if total_requests > 0:
            success_rate = success_requests / total_requests
        else:
            success_rate = 0.0

        items.append(
            ActiveProviderMetrics(
                provider_id=provider_id,
                total_requests=total_requests,
                success_requests=success_requests,
                error_requests=error_requests,
                success_rate=success_rate,
                latency_p95_ms=latency_p95_ms,
            )
        )

    overview = OverviewActiveProviders(
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        items=items,
    )

    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                overview.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to store metrics overview providers to Redis (key=%s)",
                cache_key,
            )

    return overview


@router.get(
    "/overview/timeseries",
    response_model=OverviewMetricsTimeSeries,
    summary="仪表盘概览：全局请求时间序列（近期活动）",
)
async def get_overview_timeseries(
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    bucket: Literal["minute"] = Query(
        "minute",
        description="时间粒度，目前仅支持 minute（按分钟聚合）",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> OverviewMetricsTimeSeries:
    """
    返回全局请求的时间序列，用于“近期活动”图表。

    与 /metrics/providers/timeseries 类似，但按全局维度聚合。
    """
    if bucket != MetricsBucket.MINUTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 bucket=minute",
        )

    cache_key = f"metrics:overview:timeseries:{time_range}:{transport}:{is_stream}:{bucket}"

    if redis is not object:  # pragma: no branch
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to load metrics overview timeseries from Redis (key=%s)",
                cache_key,
            )
            cached = None
        if cached:
            try:
                return OverviewMetricsTimeSeries.model_validate(cached)
            except Exception:  # pragma: no cover - 防御性日志
                logger.exception(
                    "Cached metrics overview timeseries is malformed, ignoring (key=%s)",
                    cache_key,
                )

    start_at = _resolve_time_range(time_range)

    stmt = select(
        ProviderRoutingMetricsHistory.window_start,
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.total_requests_1m),
            0,
        ),
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.success_requests),
            0,
        ),
        func.coalesce(
            func.sum(ProviderRoutingMetricsHistory.error_requests),
            0,
        ),
        func.sum(
            ProviderRoutingMetricsHistory.latency_avg_ms
            * ProviderRoutingMetricsHistory.total_requests_1m
        ).label("lat_sum"),
        func.sum(ProviderRoutingMetricsHistory.total_requests_1m).label(
            "weight_sum"
        ),
        func.sum(
            ProviderRoutingMetricsHistory.latency_p95_ms
            * ProviderRoutingMetricsHistory.total_requests_1m
        ).label("lat_p95_sum"),
        func.sum(
            ProviderRoutingMetricsHistory.latency_p99_ms
            * ProviderRoutingMetricsHistory.total_requests_1m
        ).label("lat_p99_sum"),
    ).group_by(ProviderRoutingMetricsHistory.window_start)

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    stmt = stmt.order_by(ProviderRoutingMetricsHistory.window_start.asc())

    try:
        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception("Failed to load metrics overview timeseries")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load metrics overview timeseries",
        )

    points: list[MetricsDataPoint] = []
    for row in rows:
        window_start = row[0]
        total_requests = int(row[1] or 0)
        success_requests = int(row[2] or 0)
        error_requests = int(row[3] or 0)
        lat_sum = row.lat_sum
        weight_sum = row.weight_sum or 0
        lat_p95_sum = row.lat_p95_sum
        lat_p99_sum = row.lat_p99_sum

        if total_requests > 0 and weight_sum:
            latency_avg_ms = float(lat_sum / weight_sum) if lat_sum is not None else 0.0
            latency_p95_ms = (
                float(lat_p95_sum / weight_sum) if lat_p95_sum is not None else latency_avg_ms
            )
            latency_p99_ms = (
                float(lat_p99_sum / weight_sum) if lat_p99_sum is not None else latency_p95_ms
            )
            error_rate = error_requests / total_requests
        else:
            latency_avg_ms = 0.0
            latency_p95_ms = 0.0
            latency_p99_ms = 0.0
            error_rate = 0.0

        points.append(
            MetricsDataPoint(
                window_start=window_start,
                total_requests=total_requests,
                success_requests=success_requests,
                error_requests=error_requests,
                latency_avg_ms=latency_avg_ms,
                latency_p95_ms=latency_p95_ms,
                latency_p99_ms=latency_p99_ms,
                error_rate=error_rate,
            )
        )

    result = OverviewMetricsTimeSeries(
        time_range=time_range,
        bucket=bucket,
        transport=transport,
        is_stream=is_stream,
        points=points,
    )

    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                result.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to store metrics overview timeseries to Redis (key=%s)",
                cache_key,
            )

    return result


@router.get(
    "/user-overview/summary",
    response_model=UserOverviewMetricsSummary,
    summary="仪表盘概览（用户维度）：请求量 / 成功率 / 活跃 Provider 汇总",
)
async def get_user_overview_summary(
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query("all"),
    is_stream: Literal["true", "false", "all"] = Query("all"),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> UserOverviewMetricsSummary:
    user_uuid = UUID(current_user.id)
    cache_key = f"metrics:user-overview:summary:{current_user.id}:{time_range}:{transport}:{is_stream}"

    if redis is not object:  # pragma: no branch
        try:
            cached = await redis_get_json(redis, cache_key)
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to load user overview summary cache (key=%s)",
                cache_key,
            )
            cached = None

        if cached:
            try:
                return UserOverviewMetricsSummary.model_validate(cached)
            except Exception:  # pragma: no cover
                logger.exception(
                    "Malformed user overview summary cache (key=%s)",
                    cache_key,
                )

    current_range, prev_range = _compute_overview_windows(time_range)

    def _load_window(
        window: tuple[dt.datetime | None, dt.datetime | None] | None,
    ) -> tuple[int, int, int, int]:
        if window is None:
            return 0, 0, 0, 0
        start_at, end_at = window
        stmt = _build_user_overview_stmt(
            user_id=user_uuid,
            start_at=start_at,
            end_at=end_at,
            transport=transport,
            is_stream=is_stream,
        )
        row = db.execute(stmt).one()
        total_requests = int(row.total_requests or 0)
        success_requests = int(row.success_requests or 0)
        error_requests = int(row.error_requests or 0)
        active_providers = int(row.active_providers or 0)
        return total_requests, success_requests, error_requests, active_providers

    try:
        (
            total_requests,
            success_requests,
            error_requests,
            active_providers,
        ) = _load_window(current_range)
        if prev_range is not None:
            (
                total_requests_prev,
                success_requests_prev,
                error_requests_prev,
                active_providers_prev,
            ) = _load_window(prev_range)
        else:
            total_requests_prev = None
            success_requests_prev = None
            error_requests_prev = None
            active_providers_prev = None
    except Exception:  # pragma: no cover
        logger.exception("Failed to load user metrics overview summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user overview summary",
        )

    success_rate = success_requests / total_requests if total_requests > 0 else 0.0
    if total_requests_prev and total_requests_prev > 0:
        success_rate_prev: float | None = success_requests_prev / total_requests_prev  # type: ignore[operator]
    else:
        success_rate_prev = None

    overview = UserOverviewMetricsSummary(
        user_id=current_user.id,
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        total_requests=total_requests,
        success_requests=success_requests,
        error_requests=error_requests,
        success_rate=success_rate,
        total_requests_prev=total_requests_prev,
        success_requests_prev=success_requests_prev,
        error_requests_prev=error_requests_prev,
        success_rate_prev=success_rate_prev,
        active_providers=active_providers,
        active_providers_prev=active_providers_prev,
    )

    if redis is not object:
        try:
            await redis_set_json(
                redis,
                cache_key,
                overview.model_dump(),
                ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "Failed to store user overview summary to Redis (key=%s)",
                cache_key,
            )

    return overview


@router.get(
    "/providers/summary",
    response_model=ProviderMetricsSummary,
    summary="获取指定 Provider + 逻辑模型在时间范围内的汇总指标",
)
def get_provider_summary(
    provider_id: str = Query(..., description="厂商 ID，例如 openai"),
    logical_model: str = Query(..., description="逻辑模型 ID，例如 gpt-4"),
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    user_id: str | None = Query(
        None,
        description="用户 ID，若提供则仅统计该用户",
    ),
    api_key_id: str | None = Query(
        None,
        description="API Key ID，若提供则仅统计该密钥",
    ),
    db: Session = Depends(get_db_session),
) -> ProviderMetricsSummary:
    """
    返回指定 provider + logical_model 在给定时间范围内的汇总指标。
    """
    start_at = _resolve_time_range(time_range)

    stmt = (
        select(
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_requests_1m), 0),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.success_requests), 0),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_requests), 0),
            # 使用加权平均：sum(latency_avg_ms * total_requests) / sum(total_requests)
            func.sum(
                ProviderRoutingMetricsHistory.latency_avg_ms
                * ProviderRoutingMetricsHistory.total_requests_1m
            ).label("lat_sum"),
            func.sum(ProviderRoutingMetricsHistory.total_requests_1m).label(
                "weight_sum"
            ),
        )
        .where(
            ProviderRoutingMetricsHistory.provider_id == provider_id,
            ProviderRoutingMetricsHistory.logical_model == logical_model,
        )
    )

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    if user_id:
        stmt = stmt.where(ProviderRoutingMetricsHistory.user_id == user_id)

    if api_key_id:
        stmt = stmt.where(ProviderRoutingMetricsHistory.api_key_id == api_key_id)

    try:
        row = db.execute(stmt).one()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to load metrics summary for provider=%s logical_model=%s",
            provider_id,
            logical_model,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load metrics summary",
        )

    total_requests = int(row[0] or 0)
    success_requests = int(row[1] or 0)
    error_requests = int(row[2] or 0)
    lat_sum = row[3]
    weight_sum = row[4] or 0

    if total_requests > 0 and weight_sum:
        latency_avg_ms: float | None = float(lat_sum / weight_sum)
        error_rate = error_requests / total_requests
    else:
        latency_avg_ms = None
        error_rate = 0.0

    return ProviderMetricsSummary(
        provider_id=provider_id,
        logical_model=logical_model,
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        user_id=user_id,
        api_key_id=api_key_id,
        total_requests=total_requests,
        success_requests=success_requests,
        error_requests=error_requests,
        error_rate=error_rate,
        latency_avg_ms=latency_avg_ms,
    )


@router.get(
    "/users/summary",
    response_model=UserMetricsSummary,
    summary="按用户汇总指标（跨 Provider 与 Logical Model）",
)
def get_user_summary(
    user_id: str = Query(..., description="用户 ID（UUID）"),
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    db: Session = Depends(get_db_session),
) -> UserMetricsSummary:
    """
    按 user_id 聚合指定时间范围内的调用指标，跨 Provider 与 Logical Model。
    """
    start_at = _resolve_time_range(time_range)

    stmt = (
        select(
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_requests_1m), 0),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.success_requests), 0),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_requests), 0),
            func.sum(
                ProviderRoutingMetricsHistory.latency_avg_ms
                * ProviderRoutingMetricsHistory.total_requests_1m
            ).label("lat_sum"),
            func.sum(ProviderRoutingMetricsHistory.total_requests_1m).label(
                "weight_sum"
            ),
        )
        .where(ProviderRoutingMetricsHistory.user_id == UUID(user_id))
    )

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    try:
        row = db.execute(stmt).one()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to load user metrics summary for user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user metrics summary",
        )

    total_requests = int(row[0] or 0)
    success_requests = int(row[1] or 0)
    error_requests = int(row[2] or 0)
    lat_sum = row[3]
    weight_sum = row[4] or 0

    if total_requests > 0 and weight_sum:
        latency_avg_ms: float | None = float(lat_sum / weight_sum)
        error_rate = error_requests / total_requests
    else:
        latency_avg_ms = None
        error_rate = 0.0

    return UserMetricsSummary(
        user_id=user_id,
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        total_requests=total_requests,
        success_requests=success_requests,
        error_requests=error_requests,
        error_rate=error_rate,
        latency_avg_ms=latency_avg_ms,
    )


@router.get(
    "/api-keys/summary",
    response_model=APIKeyMetricsSummary,
    summary="按 API Key 汇总指标（跨 Provider 与 Logical Model）",
)
def get_api_key_summary(
    api_key_id: str = Query(..., description="API Key ID（UUID）"),
    time_range: Literal["today", "7d", "30d", "all"] = Query(
        "7d",
        description="时间范围：today=今天, 7d=过去 7 天, 30d=过去 30 天, all=全部",
    ),
    transport: Literal["http", "sdk", "claude_cli", "all"] = Query(
        "all",
        description="传输模式过滤：http/sdk/all",
    ),
    is_stream: Literal["true", "false", "all"] = Query(
        "all",
        description="流式过滤：true（流式）/false（非流式）/all（全部）",
    ),
    db: Session = Depends(get_db_session),
) -> APIKeyMetricsSummary:
    """
    按 api_key_id 聚合指定时间范围内的调用指标，跨 Provider 与 Logical Model。
    """
    start_at = _resolve_time_range(time_range)

    stmt = (
        select(
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.total_requests_1m), 0),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.success_requests), 0),
            func.coalesce(func.sum(ProviderRoutingMetricsHistory.error_requests), 0),
            func.sum(
                ProviderRoutingMetricsHistory.latency_avg_ms
                * ProviderRoutingMetricsHistory.total_requests_1m
            ).label("lat_sum"),
            func.sum(ProviderRoutingMetricsHistory.total_requests_1m).label(
                "weight_sum"
            ),
        )
        .where(ProviderRoutingMetricsHistory.api_key_id == UUID(api_key_id))
    )

    if start_at is not None:
        stmt = stmt.where(ProviderRoutingMetricsHistory.window_start >= start_at)

    if transport != "all":
        stmt = stmt.where(ProviderRoutingMetricsHistory.transport == transport)

    if is_stream != "all":
        stmt = stmt.where(
            ProviderRoutingMetricsHistory.is_stream == (is_stream == "true")
        )

    try:
        row = db.execute(stmt).one()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to load api key metrics summary for api_key_id=%s",
            api_key_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load api key metrics summary",
        )

    total_requests = int(row[0] or 0)
    success_requests = int(row[1] or 0)
    error_requests = int(row[2] or 0)
    lat_sum = row[3]
    weight_sum = row[4] or 0

    if total_requests > 0 and weight_sum:
        latency_avg_ms: float | None = float(lat_sum / weight_sum)
        error_rate = error_requests / total_requests
    else:
        latency_avg_ms = None
        error_rate = 0.0

    return APIKeyMetricsSummary(
        api_key_id=api_key_id,
        time_range=time_range,
        transport=transport,
        is_stream=is_stream,
        total_requests=total_requests,
        success_requests=success_requests,
        error_requests=error_requests,
        error_rate=error_rate,
        latency_avg_ms=latency_avg_ms,
    )


__all__ = ["router"]
