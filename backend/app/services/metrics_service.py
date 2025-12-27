from __future__ import annotations

import datetime as dt
import time
from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.models import ProviderRoutingMetricsHistory
from app.proxy_pool import pick_upstream_proxy, report_upstream_proxy_failure
from app.services.metrics_buffer import (
    BufferedMetricsRecorder,
    BufferedUserMetricsRecorder,
    MetricsKey,
    MetricsStats,
    UserMetricsKey,
)
from app.services.upstream_proxy.utils import mask_proxy_url
from app.settings import settings
from app.upstream import UpstreamStreamError, stream_upstream

BucketSizeSeconds = Literal[60]

DEFAULT_BUCKET_SECONDS: BucketSizeSeconds = 60

metrics_recorder = BufferedMetricsRecorder(
    flush_interval_seconds=settings.metrics_flush_interval_seconds,
    latency_sample_size=settings.metrics_latency_sample_size,
    max_buffered_buckets=settings.metrics_max_buffered_buckets,
    success_sample_rate=settings.metrics_success_sample_rate,
)

user_metrics_recorder = BufferedUserMetricsRecorder(
    flush_interval_seconds=settings.metrics_flush_interval_seconds,
    latency_sample_size=settings.metrics_latency_sample_size,
    max_buffered_buckets=settings.metrics_max_buffered_buckets,
    success_sample_rate=settings.metrics_success_sample_rate,
)

if settings.metrics_buffer_enabled:
    metrics_recorder.start()
    user_metrics_recorder.start()

def _timeout_seconds(timeout_cfg: object) -> float:
    if isinstance(timeout_cfg, (int, float)):
        return float(timeout_cfg)
    if hasattr(timeout_cfg, "connect"):
        connect = timeout_cfg.connect
        if isinstance(connect, (int, float)):
            return float(connect)
    return float(settings.upstream_timeout)


def _current_bucket_start(now: dt.datetime, bucket_seconds: int) -> dt.datetime:
    """
    将当前时间截断到指定秒数的聚合桶起点（例如按分钟聚合）。
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.UTC)
    else:
        now = now.astimezone(dt.UTC)

    # 使用 timestamp 截断，支持不同桶尺寸（默认 60s）。
    epoch_seconds = int(now.timestamp())
    bucket_start = epoch_seconds - (epoch_seconds % bucket_seconds)
    return dt.datetime.fromtimestamp(bucket_start, tz=dt.UTC)


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
    status_code: int | None = None,
    error_kind: str | None = None,
    bucket_seconds: int = DEFAULT_BUCKET_SECONDS,
) -> None:
    """
    将单次上游调用累加到本地缓冲区，由后台批量写入 provider_routing_metrics_history。

    - 默认开启指标缓冲：减少每次请求的同步写库开销。
    - 若关闭缓冲（METRICS_BUFFER_ENABLED=false），退化为立即 UPSERT。
    """
    try:
        now = dt.datetime.now(tz=dt.UTC)
        window_start = _current_bucket_start(now, bucket_seconds)

        resolved_error_kind = error_kind
        if not success and resolved_error_kind is None:
            if status_code == 429:
                resolved_error_kind = "429"
            elif status_code is None:
                resolved_error_kind = "timeout"
            elif 400 <= status_code < 500:
                resolved_error_kind = "4xx"
            elif 500 <= status_code < 600:
                resolved_error_kind = "5xx"

        if settings.metrics_buffer_enabled:
            metrics_recorder.record_sample(
                provider_id=provider_id,
                logical_model=logical_model,
                transport=transport,
                is_stream=is_stream,
                user_id=user_id,
                api_key_id=api_key_id,
                window_start=window_start,
                bucket_seconds=bucket_seconds,
                success=success,
                latency_ms=latency_ms,
                error_kind=resolved_error_kind,
            )
            if user_id is not None:
                _record_user_metrics_buffered(
                    user_id=user_id,
                    provider_id=provider_id,
                    logical_model=logical_model,
                    transport=transport,
                    is_stream=is_stream,
                    window_start=window_start,
                    bucket_seconds=bucket_seconds,
                    success=success,
                    latency_ms=latency_ms,
                )
            return

        # 缓冲关闭时，直接写库（保留旧逻辑）。
        stats = MetricsStats()
        stats.record(
            success=success,
            latency_ms=latency_ms,
            sample_limit=1,
            error_kind=resolved_error_kind,
        )
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
        immediate_stmt = metrics_recorder._build_upsert_stmt(key, stats)
        db.execute(immediate_stmt)

        if user_id is not None:
            _record_user_metrics_immediate(
                db,
                user_id=user_id,
                provider_id=provider_id,
                logical_model=logical_model,
                transport=transport,
                is_stream=is_stream,
                window_start=window_start,
                bucket_seconds=bucket_seconds,
                success=success,
                latency_ms=latency_ms,
            )

        db.commit()
    except Exception:  # pragma: no cover - 防御性日志，不影响主流程
        logger.exception(
            "Failed to record provider metrics for provider=%s logical_model=%s",
            provider_id,
            logical_model,
        )


def record_provider_token_usage(
    db: Session,
    *,
    provider_id: str,
    logical_model: str,
    transport: str,
    is_stream: bool,
    user_id: UUID | None,
    api_key_id: UUID | None,
    occurred_at: dt.datetime | None,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    estimated: bool,
    bucket_seconds: int = DEFAULT_BUCKET_SECONDS,
) -> None:
    """
    记录 Token 用量到分钟桶事实表（不依赖扣费是否发生）。

    该写入可能发生在异步计费任务中，因此允许“先插入占位行，再由后续指标写入补齐”。
    """
    if not provider_id or not logical_model:
        return
    if total_tokens is None:
        return

    try:
        at = occurred_at or dt.datetime.now(tz=dt.UTC)
        window_start = _current_bucket_start(at, bucket_seconds)

        in_tokens = int(input_tokens or 0)
        out_tokens = int(output_tokens or 0)
        tot_tokens = int(total_tokens or 0)
        if tot_tokens < 0:
            return

        dialect_name = getattr(db.get_bind(), "dialect", None)
        dialect_name = getattr(dialect_name, "name", None)
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as upsert_insert

            conflict_kwargs = {"constraint": "uq_provider_routing_metrics_history_bucket"}
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert_insert

            conflict_kwargs = {
                "index_elements": [
                    ProviderRoutingMetricsHistory.provider_id,
                    ProviderRoutingMetricsHistory.logical_model,
                    ProviderRoutingMetricsHistory.transport,
                    ProviderRoutingMetricsHistory.is_stream,
                    ProviderRoutingMetricsHistory.user_id,
                    ProviderRoutingMetricsHistory.api_key_id,
                    ProviderRoutingMetricsHistory.window_start,
                ]
            }

        insert_stmt = upsert_insert(ProviderRoutingMetricsHistory).values(
            provider_id=provider_id,
            logical_model=logical_model,
            transport=transport,
            is_stream=bool(is_stream),
            user_id=user_id,
            api_key_id=api_key_id,
            window_start=window_start,
            window_duration=bucket_seconds,
            total_requests_1m=0,
            success_requests=0,
            error_requests=0,
            latency_avg_ms=0.0,
            latency_p50_ms=0.0,
            latency_p95_ms=0.0,
            latency_p99_ms=0.0,
            error_rate=0.0,
            success_qps_1m=0.0,
            status="healthy",
            input_tokens_sum=in_tokens,
            output_tokens_sum=out_tokens,
            total_tokens_sum=tot_tokens,
            token_estimated_requests=1 if estimated else 0,
        )

        update_stmt = insert_stmt.on_conflict_do_update(
            **conflict_kwargs,
            set_={
                "input_tokens_sum": ProviderRoutingMetricsHistory.input_tokens_sum + in_tokens,
                "output_tokens_sum": ProviderRoutingMetricsHistory.output_tokens_sum + out_tokens,
                "total_tokens_sum": ProviderRoutingMetricsHistory.total_tokens_sum + tot_tokens,
                "token_estimated_requests": ProviderRoutingMetricsHistory.token_estimated_requests
                + (1 if estimated else 0),
            },
        )
        db.execute(update_stmt)
        db.commit()
    except Exception:  # pragma: no cover - 指标写入失败不影响主流程
        db.rollback()
        logger.exception(
            "Failed to record token usage for provider=%s logical_model=%s",
            provider_id,
            logical_model,
        )


def flush_metrics_buffer() -> int:
    """手动触发一次缓冲刷新，便于调试或关停前落盘。"""
    return metrics_recorder.flush()


def flush_user_metrics_buffer() -> int:
    """手动触发一次用户维度指标的缓冲刷新。"""
    return user_metrics_recorder.flush()


def _record_user_metrics_buffered(
    *,
    user_id: UUID,
    provider_id: str,
    logical_model: str,
    transport: str,
    is_stream: bool,
    window_start: dt.datetime,
    bucket_seconds: int,
    success: bool,
    latency_ms: float,
) -> None:
    try:
        user_metrics_recorder.record_sample(
            user_id=user_id,
            provider_id=provider_id,
            logical_model=logical_model,
            transport=transport,
            is_stream=is_stream,
            window_start=window_start,
            bucket_seconds=bucket_seconds,
            success=success,
            latency_ms=latency_ms,
        )
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to buffer user metrics for user=%s provider=%s model=%s",
            user_id,
            provider_id,
            logical_model,
        )


def _record_user_metrics_immediate(
    db: Session,
    *,
    user_id: UUID,
    provider_id: str,
    logical_model: str,
    transport: str,
    is_stream: bool,
    window_start: dt.datetime,
    bucket_seconds: int,
    success: bool,
    latency_ms: float,
) -> None:
    stats = MetricsStats()
    stats.record(success=success, latency_ms=latency_ms, sample_limit=1, error_kind=None)
    key = UserMetricsKey(
        user_id=user_id,
        provider_id=provider_id,
        logical_model=logical_model,
        transport=transport,
        is_stream=is_stream,
        window_start=window_start,
        bucket_seconds=bucket_seconds,
    )
    stmt = user_metrics_recorder._build_upsert_stmt(key, stats)
    db.execute(stmt)


async def call_upstream_http_with_metrics(
    *,
    client: CurlCffiClient | httpx.AsyncClient,
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
    status_code: int | None = None
    error_kind: str | None = None
    proxy_url = await pick_upstream_proxy()
    timeout_cfg = _timeout_seconds(getattr(client, "timeout", settings.upstream_timeout))
    try:
        if proxy_url:
            max_attempts = settings.upstream_proxy_max_retries + 1
            tried: set[str] = set()
            last_exc: httpx.HTTPError | None = None
            for attempt in range(max_attempts):
                if attempt == 0:
                    current_proxy = proxy_url
                else:
                    current_proxy = await pick_upstream_proxy(exclude=tried)
                if not current_proxy:
                    break
                tried.add(current_proxy)
                logger.info(
                    "call_upstream_http_with_metrics: 使用代理 %s 请求上游 %s (provider=%s logical_model=%s attempt=%d/%d)",
                    mask_proxy_url(current_proxy),
                    url,
                    provider_id,
                    logical_model,
                    attempt + 1,
                    max_attempts,
                )
                try:
                    async with httpx.AsyncClient(
                        timeout=timeout_cfg,
                        proxy=current_proxy,
                        trust_env=True,
                    ) as proxy_client:
                        resp = await proxy_client.post(
                            url,
                            headers=headers,
                            json=json_body,
                        )
                    success = resp.status_code < 400
                    logger.info(
                        "call_upstream_http_with_metrics: 代理 %s 请求成功 (provider=%s logical_model=%s status=%d)",
                        mask_proxy_url(current_proxy),
                        provider_id,
                        logical_model,
                        resp.status_code,
                    )
                    return resp
                except httpx.HTTPError as exc:
                    last_exc = exc
                    await report_upstream_proxy_failure(current_proxy)
                    if attempt + 1 < max_attempts:
                        logger.warning(
                            "call_upstream_http_with_metrics: 代理 %s 请求失败，将换代理重试 (%d/%d): %s",
                            mask_proxy_url(current_proxy),
                            attempt + 2,
                            max_attempts,
                            exc,
                        )
                        continue
                    raise
            if last_exc:
                raise last_exc
            # 代理池为空或不可用时回退直连
            logger.info(
                "call_upstream_http_with_metrics: 代理池不可用,使用直连请求上游 %s (provider=%s logical_model=%s)",
                url,
                provider_id,
                logical_model,
            )
            resp = await client.post(url, headers=headers, json=json_body)
        else:
            logger.info(
                "call_upstream_http_with_metrics: 未启用代理,使用直连请求上游 %s (provider=%s logical_model=%s)",
                url,
                provider_id,
                logical_model,
            )
            resp = await client.post(url, headers=headers, json=json_body)
        status_code = resp.status_code
        success = resp.status_code < 400
        logger.info(
            "call_upstream_http_with_metrics: 直连请求成功 (provider=%s logical_model=%s status=%d)",
            provider_id,
            logical_model,
            resp.status_code,
        )
        return resp
    except httpx.TimeoutException as exc:
        error_kind = "timeout"
        logger.warning(
            "Upstream HTTP timeout for %s (provider=%s): %s",
            url,
            provider_id,
            exc,
        )
        raise
    except httpx.HTTPError as exc:
        error_kind = "timeout"
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
                status_code=status_code,
                error_kind=error_kind,
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
    client: CurlCffiClient | httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, object],
    redis,
    session_id: str | None,
    sse_style: str | None = None,
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
    proxy_url = await pick_upstream_proxy()
    timeout_cfg = _timeout_seconds(getattr(client, "timeout", settings.upstream_timeout))

    try:
        if proxy_url:
            max_attempts = settings.upstream_proxy_max_retries + 1
            tried: set[str] = set()
            last_err: UpstreamStreamError | None = None
            for attempt in range(max_attempts):
                if attempt == 0:
                    current_proxy = proxy_url
                else:
                    current_proxy = await pick_upstream_proxy(exclude=tried)
                if not current_proxy:
                    break
                tried.add(current_proxy)
                logger.info(
                    "stream_upstream_with_metrics: 使用代理 %s 连接上游 %s (provider=%s logical_model=%s attempt=%d/%d)",
                    mask_proxy_url(current_proxy),
                    url,
                    provider_id,
                    logical_model,
                    attempt + 1,
                    max_attempts,
                )
                try:
                    async with httpx.AsyncClient(
                        timeout=timeout_cfg,
                        proxy=current_proxy,
                        trust_env=True,
                    ) as proxy_client:
                        async for chunk in stream_upstream(
                            client=proxy_client,
                            method=method,
                            url=url,
                            headers=headers,
                            json_body=json_body,
                            redis=redis,
                            session_id=session_id,
                            sse_style=sse_style,
                        ):
                            if not first_chunk_seen:
                                first_chunk_seen = True
                                latency_ms = (time.perf_counter() - start) * 1000.0
                                logger.info(
                                    "stream_upstream_with_metrics: 代理 %s 首包到达 (provider=%s logical_model=%s ttfb=%.2fms)",
                                    mask_proxy_url(current_proxy),
                                    provider_id,
                                    logical_model,
                                    latency_ms,
                                )
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
                    return
                except UpstreamStreamError as err:
                    last_err = err
                    # 仅在“连接/代理传输错误（status_code=None）”时换代理重试
                    if err.status_code is None and attempt + 1 < max_attempts:
                        await report_upstream_proxy_failure(current_proxy)
                        logger.warning(
                            "stream_upstream_with_metrics: 代理 %s 连接失败，将换代理重试 (%d/%d): %s",
                            mask_proxy_url(current_proxy),
                            attempt + 2,
                            max_attempts,
                            err.text,
                        )
                        continue
                    raise
            if last_err:
                raise last_err
            # 代理池不可用时回退直连
            logger.info(
                "stream_upstream_with_metrics: 代理池不可用,使用直连连接上游 %s (provider=%s logical_model=%s)",
                url,
                provider_id,
                logical_model,
            )
            async for chunk in stream_upstream(
                client=client,
                method=method,
                url=url,
                headers=headers,
                json_body=json_body,
                redis=redis,
                session_id=session_id,
                sse_style=sse_style,
            ):
                if not first_chunk_seen:
                    first_chunk_seen = True
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    logger.info(
                        "stream_upstream_with_metrics: 直连首包到达 (provider=%s logical_model=%s ttfb=%.2fms)",
                        provider_id,
                        logical_model,
                        latency_ms,
                    )
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
            return
        else:
            logger.info(
                "stream_upstream_with_metrics: 未启用代理,使用直连连接上游 %s (provider=%s logical_model=%s)",
                url,
                provider_id,
                logical_model,
            )
            async for chunk in stream_upstream(
                client=client,
                method=method,
                url=url,
                headers=headers,
                json_body=json_body,
                redis=redis,
                session_id=session_id,
                sse_style=sse_style,
            ):
                if not first_chunk_seen:
                    first_chunk_seen = True
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    logger.info(
                        "stream_upstream_with_metrics: 直连首包到达 (provider=%s logical_model=%s ttfb=%.2fms)",
                        provider_id,
                        logical_model,
                        latency_ms,
                    )
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
                status_code=err.status_code,
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
    err: Exception | None = None
    try:
        result = await driver.generate_content(
            api_key=api_key,
            model_id=model_id,
            payload=payload,
            base_url=base_url,
        )
        success = True
        return result
    except Exception as exc:
        err = exc
        raise
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
                error_kind="timeout" if (err is not None and not success) else None,
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
                    error_kind="timeout",
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
    "call_sdk_generate_with_metrics",
    "call_upstream_http_with_metrics",
    "flush_metrics_buffer",
    "flush_user_metrics_buffer",
    "record_provider_call_metric",
    "record_provider_token_usage",
    "stream_sdk_with_metrics",
    "stream_upstream_with_metrics",
]
