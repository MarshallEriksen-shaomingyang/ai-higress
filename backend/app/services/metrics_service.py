from __future__ import annotations

import datetime as dt
import time
from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import UUID

import httpx

from sqlalchemy import Float, cast
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import ProviderRoutingMetricsHistory
from app.upstream import UpstreamStreamError, stream_upstream

BucketSizeSeconds = Literal[60]

DEFAULT_BUCKET_SECONDS: BucketSizeSeconds = 60


def _current_bucket_start(now: dt.datetime, bucket_seconds: int) -> dt.datetime:
    """
    将当前时间截断到指定秒数的聚合桶起点（例如按分钟聚合）。
    """
    # 统一使用 UTC，避免跨时区聚合混乱。
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    else:
        now = now.astimezone(dt.timezone.utc)

    # 这里只做到“分钟起点”的截断，便于和人类时间对齐。
    floored = now.replace(second=0, microsecond=0)
    return floored


def record_provider_call_metric(
    db: Session,
    *,
    provider_id: str,
    logical_model: str,
    transport: str,
    is_stream: bool,
    user_id: UUID | None,
    api_key_id: UUID | None,
    success: bool,
    latency_ms: float,
    bucket_seconds: int = DEFAULT_BUCKET_SECONDS,
) -> None:
    """
    将单次上游调用累加到 provider_routing_metrics_history 的时间桶里。

    设计目标：
    - 每次调用只做一次 INSERT ... ON CONFLICT DO UPDATE，写入成本可控；
    - 先聚合出“调用次数 + 平均延迟 + 错误率”，满足报表/趋势图需求；
    - p95/p99 先简单用平均值占位，后续可以改为离线/异步精细计算。
    """
    try:
        now = dt.datetime.now(tz=dt.timezone.utc)
        window_start = _current_bucket_start(now, bucket_seconds)

        success_inc = 1 if success else 0
        error_inc = 0 if success else 1

        base_insert = insert(ProviderRoutingMetricsHistory).values(
            provider_id=provider_id,
            logical_model=logical_model,
            transport=transport,
            is_stream=is_stream,
            user_id=user_id,
            api_key_id=api_key_id,
            window_start=window_start,
            window_duration=bucket_seconds,
            total_requests_1m=1,
            success_requests=success_inc,
            error_requests=error_inc,
            latency_avg_ms=latency_ms,
            # 先使用平均值占位，后续可通过离线任务更新为真实 p95/p99。
            latency_p95_ms=latency_ms,
            latency_p99_ms=latency_ms,
            error_rate=float(error_inc),
            success_qps_1m=success_inc / bucket_seconds,
            status="healthy",
        )

        # on_conflict 里基于当前行做累加与派生指标更新。
        new_total = ProviderRoutingMetricsHistory.total_requests_1m + 1
        new_success = ProviderRoutingMetricsHistory.success_requests + success_inc
        new_error = ProviderRoutingMetricsHistory.error_requests + error_inc

        update_stmt = base_insert.on_conflict_do_update(
            constraint="uq_provider_routing_metrics_history_bucket",
            set_={
                "total_requests_1m": new_total,
                "success_requests": new_success,
                "error_requests": new_error,
                # 简单的加权平均： (旧均值 * 旧总数 + 本次延迟) / 新总数
                "latency_avg_ms": (
                    (
                        ProviderRoutingMetricsHistory.latency_avg_ms
                        * ProviderRoutingMetricsHistory.total_requests_1m
                        + latency_ms
                    )
                    / cast(new_total, Float)
                ),
                # 先用平均值占位，后续可以通过离线任务离线刷新真实 P95/P99。
                "latency_p95_ms": (
                    (
                        ProviderRoutingMetricsHistory.latency_avg_ms
                        * ProviderRoutingMetricsHistory.total_requests_1m
                        + latency_ms
                    )
                    / cast(new_total, Float)
                ),
                "latency_p99_ms": (
                    (
                        ProviderRoutingMetricsHistory.latency_avg_ms
                        * ProviderRoutingMetricsHistory.total_requests_1m
                        + latency_ms
                    )
                    / cast(new_total, Float)
                ),
                "error_rate": cast(new_error, Float) / cast(new_total, Float),
                "success_qps_1m": cast(new_success, Float) / float(bucket_seconds),
                # 暂时统一认为“healthy”，后续可按错误率/延迟派生。
                "status": ProviderRoutingMetricsHistory.status,
            },
        )

        db.execute(update_stmt)
        db.commit()
    except Exception:  # pragma: no cover - 防御性日志，不影响主流程
        logger.exception(
            "Failed to record provider metrics for provider=%s logical_model=%s",
            provider_id,
            logical_model,
        )


async def call_upstream_http_with_metrics(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, object],
    db: Session,
    provider_id: str,
    logical_model: str,
    user_id: UUID | None = None,
    api_key_id: UUID | None = None,
) -> httpx.Response:
    """
    统一封装上游 HTTP 调用 + 指标打点。

    - 成功：HTTP 状态码 < 400；
    - 失败：请求抛出 httpx.HTTPError 或返回状态码 >= 400。
    """
    start = time.perf_counter()
    success = False
    try:
        resp = await client.post(url, headers=headers, json=json_body)
        success = resp.status_code < 400
        return resp
    except httpx.HTTPError as exc:
        logger.warning(
            "Upstream HTTP error for %s (provider=%s): %s",
            url,
            provider_id,
            exc,
        )
        raise
    finally:
        latency_ms = (time.perf_counter() - start) * 1000.0
        try:
            record_provider_call_metric(
                db,
                provider_id=provider_id,
                logical_model=logical_model,
                transport="http",
                is_stream=False,
                user_id=user_id,
                api_key_id=api_key_id,
                success=success,
                latency_ms=latency_ms,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "record_provider_call_metric failed in call_upstream_http_with_metrics "
                "for provider=%s logical_model=%s",
                provider_id,
                logical_model,
            )


async def stream_upstream_with_metrics(
    *,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, object],
    redis,
    session_id: str | None,
    db: Session,
    provider_id: str,
    logical_model: str,
    user_id: UUID | None = None,
    api_key_id: UUID | None = None,
) -> AsyncIterator[bytes]:
    """
    封装流式上游请求 + 指标打点。

    约定：
    - 若在收到任何 chunk 之前抛出 UpstreamStreamError，则视为一次失败调用；
    - 若至少收到一个 chunk，则视为成功调用，延迟取“首包到达时间”（TTFB）。
    """
    start = time.perf_counter()
    first_chunk_seen = False

    try:
        async for chunk in stream_upstream(
            client=client,
            method=method,
            url=url,
            headers=headers,
            json_body=json_body,
            redis=redis,
            session_id=session_id,
        ):
            if not first_chunk_seen:
                first_chunk_seen = True
                latency_ms = (time.perf_counter() - start) * 1000.0
                try:
                    record_provider_call_metric(
                        db,
                        provider_id=provider_id,
                        logical_model=logical_model,
                        transport="http",
                        is_stream=True,
                        user_id=user_id,
                        api_key_id=api_key_id,
                        success=True,
                        latency_ms=latency_ms,
                    )
                except Exception:  # pragma: no cover - 防御性日志
                    logger.exception(
                        "record_provider_call_metric failed in stream_upstream_with_metrics "
                        "for provider=%s logical_model=%s (first chunk)",
                        provider_id,
                        logical_model,
                    )
            yield chunk
    except UpstreamStreamError as err:
        latency_ms = (time.perf_counter() - start) * 1000.0
        try:
            record_provider_call_metric(
                db,
                provider_id=provider_id,
                logical_model=logical_model,
                transport="http",
                is_stream=True,
                user_id=user_id,
                api_key_id=api_key_id,
                success=False,
                latency_ms=latency_ms,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "record_provider_call_metric failed in stream_upstream_with_metrics "
                "for provider=%s logical_model=%s (UpstreamStreamError)",
                provider_id,
                logical_model,
            )
        # 将错误重新抛给调用方，保持原有路由控制逻辑。
        raise


async def call_sdk_generate_with_metrics(
    *,
    driver: Any,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str,
    db: Session,
    provider_id: str,
    logical_model: str,
    user_id: UUID | None = None,
    api_key_id: UUID | None = None,
) -> Any:
    """
    封装 SDK 模式 generate_content 调用 + 指标打点。

    - SDK 视角下不存在 HTTP 状态码，这里统一认为调用成功即 success=True；
    - 若 driver.generate_content 抛出异常，则视为一次失败调用。
    """
    start = time.perf_counter()
    success = False
    try:
        result = await driver.generate_content(
            api_key=api_key,
            model_id=model_id,
            payload=payload,
            base_url=base_url,
        )
        success = True
        return result
    finally:
        latency_ms = (time.perf_counter() - start) * 1000.0
        try:
            record_provider_call_metric(
                db,
                provider_id=provider_id,
                logical_model=logical_model,
                transport="sdk",
                is_stream=False,
                user_id=user_id,
                api_key_id=api_key_id,
                success=success,
                latency_ms=latency_ms,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "record_provider_call_metric failed in call_sdk_generate_with_metrics "
                "for provider=%s logical_model=%s",
                provider_id,
                logical_model,
            )


async def stream_sdk_with_metrics(
    *,
    driver: Any,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str,
    db: Session,
    provider_id: str,
    logical_model: str,
    user_id: UUID | None = None,
    api_key_id: UUID | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    封装 SDK 模式 stream_content 调用 + 指标打点。

    - 若在收到任何 chunk 之前抛出错误，则视为失败调用；
    - 若至少收到一个 chunk，则视为成功调用，延迟取“首包时间”。
    """
    start = time.perf_counter()
    first_chunk_seen = False

    try:
        async for chunk in driver.stream_content(
            api_key=api_key,
            model_id=model_id,
            payload=payload,
            base_url=base_url,
        ):
            if not first_chunk_seen:
                first_chunk_seen = True
                latency_ms = (time.perf_counter() - start) * 1000.0
                try:
                    record_provider_call_metric(
                        db,
                        provider_id=provider_id,
                        logical_model=logical_model,
                        transport="sdk",
                        is_stream=True,
                        user_id=user_id,
                        api_key_id=api_key_id,
                        success=True,
                        latency_ms=latency_ms,
                    )
                except Exception:  # pragma: no cover - 防御性日志
                    logger.exception(
                        "record_provider_call_metric failed in stream_sdk_with_metrics "
                        "for provider=%s logical_model=%s (first chunk)",
                        provider_id,
                        logical_model,
                    )
            yield chunk
    except Exception:
        # 只有在尚未收到任何 chunk 时，才将其视为失败调用。
        if not first_chunk_seen:
            latency_ms = (time.perf_counter() - start) * 1000.0
            try:
                record_provider_call_metric(
                    db,
                    provider_id=provider_id,
                    logical_model=logical_model,
                    transport="sdk",
                    is_stream=True,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    success=False,
                    latency_ms=latency_ms,
                )
            except Exception:  # pragma: no cover - 防御性日志
                logger.exception(
                    "record_provider_call_metric failed in stream_sdk_with_metrics "
                    "for provider=%s logical_model=%s (error before first chunk)",
                    provider_id,
                    logical_model,
                )
        raise


__all__ = [
    "record_provider_call_metric",
    "call_upstream_http_with_metrics",
    "stream_upstream_with_metrics",
    "call_sdk_generate_with_metrics",
    "stream_sdk_with_metrics",
]
