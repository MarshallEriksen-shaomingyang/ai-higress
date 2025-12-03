from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db_session
from app.logging_config import logger
from app.models import ProviderRoutingMetricsHistory

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_api_key)],
)


class MetricsTimeRange(str):
    TODAY = "today"
    LAST_7D = "7d"
    LAST_30D = "30d"
    ALL = "all"


class MetricsBucket(str):
    MINUTE = "minute"


class MetricsDataPoint(BaseModel):
    window_start: dt.datetime = Field(..., description="时间桶起点（UTC）")
    total_requests: int = Field(..., description="该时间桶内总请求数")
    success_requests: int = Field(..., description="成功请求数")
    error_requests: int = Field(..., description="失败请求数")
    latency_avg_ms: float = Field(..., description="平均延迟（毫秒）")
    latency_p95_ms: float = Field(..., description="P95 延迟（毫秒）")
    latency_p99_ms: float = Field(..., description="P99 延迟（毫秒）")
    error_rate: float = Field(..., description="错误率 [0,1]")


class ProviderMetricsTimeSeries(BaseModel):
    provider_id: str
    logical_model: str
    time_range: str
    bucket: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    points: list[MetricsDataPoint] = Field(default_factory=list)


class ProviderMetricsSummary(BaseModel):
    provider_id: str
    logical_model: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    user_id: str | None = Field(
        None,
        description="用户 ID 过滤（如提供则仅统计该用户，默认全部用户）",
    )
    api_key_id: str | None = Field(
        None,
        description="API Key ID 过滤（如提供则仅统计该密钥，默认全部密钥）",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    error_rate: float
    latency_avg_ms: float | None = Field(
        None,
        description="平均延迟（毫秒），无请求时为 null",
    )


class UserMetricsSummary(BaseModel):
    user_id: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    error_rate: float
    latency_avg_ms: float | None = Field(
        None,
        description="平均延迟（毫秒），无请求时为 null",
    )


class APIKeyMetricsSummary(BaseModel):
    api_key_id: str
    time_range: str
    transport: str = Field(
        "all",
        description="传输模式过滤：http/sdk/all",
    )
    is_stream: str = Field(
        "all",
        description="流式过滤：true/false/all",
    )
    total_requests: int
    success_requests: int
    error_requests: int
    error_rate: float
    latency_avg_ms: float | None = Field(
        None,
        description="平均延迟（毫秒），无请求时为 null",
    )


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
    transport: Literal["http", "sdk", "all"] = Query(
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
    transport: Literal["http", "sdk", "all"] = Query(
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
    transport: Literal["http", "sdk", "all"] = Query(
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
        .where(ProviderRoutingMetricsHistory.user_id == user_id)
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
    transport: Literal["http", "sdk", "all"] = Query(
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
        .where(ProviderRoutingMetricsHistory.api_key_id == api_key_id)
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
