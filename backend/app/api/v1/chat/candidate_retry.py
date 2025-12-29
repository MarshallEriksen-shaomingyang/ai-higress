"""
候选 Provider 重试逻辑

特点：
- 对候选列表做“按顺序尝试 + 可重试失败则切换下一个”
- 引入实时故障标记（Redis）：短时间内同一 provider 连续失败达到阈值则跳过冷却期
- 不绑定具体传输实现：通过 transport_handlers 执行（http/sdk/claude_cli）
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, TypeVar

import httpx
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from sqlalchemy.orm import Session as DbSession
from app.api.v1.chat.routing_state import RoutingStateService
from app.api.v1.chat.transport_handlers import (
    execute_claude_cli_transport,
    execute_http_transport,
    execute_sdk_transport,
)
from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.provider import config as provider_config
from app.routing.scheduler import CandidateScore
from app.schemas import PhysicalModel
from app.upstream import UpstreamStreamError, detect_request_format
from app.api.v1.chat.upstream_error_classifier import extract_error_message

C = TypeVar("C", CandidateScore, PhysicalModel)


def _unwrap_candidate(candidate: C) -> PhysicalModel:
    if isinstance(candidate, CandidateScore):
        return candidate.upstream
    return candidate


def _resolve_api_style(payload: dict[str, Any], api_style: str | None) -> str:
    if api_style:
        return api_style
    try:
        return detect_request_format(payload)
    except Exception:
        return "openai"


def _call_failure_hook(hook: Callable[..., None] | None, provider_id: str, retryable: bool) -> None:
    if hook is None:
        return
    try:
        hook(provider_id, retryable=retryable)
    except TypeError:
        hook(provider_id)


def get_provider_config(provider_id: str):
    """
    Thin wrapper to allow tests to patch `app.api.v1.chat.candidate_retry.get_provider_config`
    while still deferring to the latest implementation in `app.provider.config`.
    """
    return provider_config.get_provider_config(provider_id)


async def try_candidates_non_stream(
    *,
    candidates: Sequence[CandidateScore | PhysicalModel],
    client: httpx.AsyncClient,
    redis: Redis,
    db: DbSession,
    payload: dict[str, Any],
    logical_model_id: str,
    api_key: AuthenticatedAPIKey,
    on_success: Callable[[str, str], Awaitable[None]],
    api_style: str | None = None,
    on_failure: Callable[..., None] | None = None,
    messages_path_override: str | None = None,
    fallback_path_override: str | None = None,
    routing_state: RoutingStateService | None = None,
    request_id: str | None = None,
    attempts: list[dict[str, Any]] | None = None,
    outcome: dict[str, Any] | None = None,
) -> JSONResponse:
    resolved_style = _resolve_api_style(payload, api_style)
    state = routing_state or RoutingStateService(redis=redis)

    last_status: int | None = None
    last_error_text: str | None = None
    last_provider_id: str | None = None
    skipped_count = 0

    for idx, upstream in enumerate(candidates):
        cand = _unwrap_candidate(upstream)
        provider_id = cand.provider_id
        model_id = cand.model_id
        base_endpoint = cand.endpoint

        cooldown = await state.get_failure_cooldown_status(provider_id)
        if cooldown.should_skip:
            skipped_count += 1
            if attempts is not None:
                attempts.append(
                    {
                        "idx": idx,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "transport": None,
                        "endpoint": base_endpoint,
                        "success": False,
                        "retryable": True,
                        "skipped": True,
                        "skip_reason": "failure_cooldown",
                        "status_code": None,
                        "error_category": "failure_cooldown",
                        "error_message": None,
                        "duration_ms": 0,
                        "cooldown": {
                            "count": cooldown.count,
                            "threshold": cooldown.threshold,
                            "cooldown_seconds": cooldown.cooldown_seconds,
                        },
                    }
                )
            logger.warning(
                "candidate_retry: skipping provider %s (failures=%d/%d, cooldown=%ds)",
                provider_id,
                cooldown.count,
                cooldown.threshold,
                cooldown.cooldown_seconds,
            )
            continue

        provider_cfg = get_provider_config(provider_id)
        if provider_cfg is None:
            last_status = status.HTTP_503_SERVICE_UNAVAILABLE
            last_error_text = f"Provider '{provider_id}' is not configured"
            last_provider_id = provider_id
            if attempts is not None:
                attempts.append(
                    {
                        "idx": idx,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "transport": None,
                        "endpoint": base_endpoint,
                        "success": False,
                        "retryable": False,
                        "skipped": False,
                        "status_code": int(last_status),
                        "error_category": "provider_not_configured",
                        "error_message": extract_error_message(last_error_text),
                        "duration_ms": 0,
                    }
                )
            continue

        transport = getattr(provider_cfg, "transport", "http")
        upstream_api_style = getattr(cand, "api_style", "openai")
        attempt: dict[str, Any] | None = None
        start_attempt = time.perf_counter()
        if attempts is not None:
            attempt = {
                "idx": idx,
                "provider_id": provider_id,
                "model_id": model_id,
                "transport": str(transport),
                "endpoint": base_endpoint,
                "success": None,
                "retryable": None,
                "skipped": False,
                "status_code": None,
                "error_category": None,
                "error_message": None,
                "duration_ms": None,
            }
            attempts.append(attempt)

        if transport == "claude_cli":
            result = await execute_claude_cli_transport(
                client=client,
                redis=redis,
                db=db,
                provider_id=provider_id,
                model_id=model_id,
                payload=payload,
                logical_model_id=logical_model_id,
                api_style=resolved_style,
                api_key=api_key,
            )
        elif transport == "sdk":
            result = await execute_sdk_transport(
                redis=redis,
                db=db,
                provider_id=provider_id,
                model_id=model_id,
                payload=payload,
                logical_model_id=logical_model_id,
                api_style=resolved_style,
                api_key=api_key,
            )
        else:
            result = await execute_http_transport(
                client=client,
                redis=redis,
                db=db,
                provider_id=provider_id,
                model_id=model_id,
                url=base_endpoint,
                payload=payload,
                logical_model_id=logical_model_id,
                api_style=resolved_style,
                upstream_api_style=upstream_api_style,
                api_key=api_key,
                messages_path_override=messages_path_override,
                fallback_path_override=fallback_path_override,
            )

        duration_ms = int(max(0.0, (time.perf_counter() - start_attempt) * 1000))
        if result.success:
            await state.clear_provider_failure(provider_id)
            await on_success(provider_id, model_id)
            if attempt is not None:
                attempt.update(
                    {
                        "success": True,
                        "retryable": False,
                        "status_code": int(getattr(result.response, "status_code", 200) or 200),
                        "duration_ms": duration_ms,
                    }
                )
            if outcome is not None:
                outcome.update(
                    {
                        "success": True,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "status_code": int(getattr(result.response, "status_code", 200) or 200),
                    }
                )
            return result.response  # type: ignore[return-value]

        last_status = result.status_code
        last_error_text = result.error_text
        last_provider_id = provider_id
        penalize = bool(getattr(result, "penalize", True))
        if penalize:
            _call_failure_hook(on_failure, provider_id, bool(result.retryable))

        if penalize and result.retryable and result.status_code in (500, 502, 503, 504, 429):
            await state.increment_provider_failure(provider_id)

        if attempt is not None:
            attempt.update(
                {
                    "success": False,
                    "retryable": bool(result.retryable),
                    "status_code": result.status_code,
                    "error_category": getattr(result, "error_category", None),
                    "error_message": extract_error_message(result.error_text)[:2000],
                    "duration_ms": duration_ms,
                }
            )

        if result.retryable:
            continue

        message = extract_error_message(result.error_text)
        category = str(getattr(result, "error_category", "") or "").strip()
        detail = (
            f"Upstream error provider={provider_id} upstream_status={result.status_code}"
            f"{' category=' + category if category else ''}"
            f"{' request_id=' + request_id if request_id else ''}: {message}"
        )
        if outcome is not None:
            outcome.update(
                {
                    "success": False,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "status_code": int(status.HTTP_502_BAD_GATEWAY),
                    "upstream_status": result.status_code,
                    "error_category": category or None,
                    "error_message": message[:2000],
                }
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )

    message = f"All upstream providers failed for logical model '{logical_model_id}'"
    details: list[str] = []
    if request_id:
        details.append(f"request_id={request_id}")
    if skipped_count:
        details.append(f"skipped={skipped_count} (in failure cooldown)")
    if last_provider_id:
        details.append(f"last_provider={last_provider_id}")
    if last_status is not None:
        details.append(f"last_status={last_status}")
    if last_error_text:
        details.append(f"last_error={extract_error_message(last_error_text)}")
    detail_text = message if not details else f"{message}; " + ", ".join(details)
    if outcome is not None:
        outcome.update(
            {
                "success": False,
                "provider_id": last_provider_id,
                "status_code": int(status.HTTP_502_BAD_GATEWAY),
                "upstream_status": last_status,
                "error_message": extract_error_message(last_error_text)[:2000] if last_error_text else None,
            }
        )
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail_text)


def _is_stream_error_retryable(exc: Exception, status_code: int | None) -> bool:
    retryable_attr = getattr(exc, "retryable", None)
    if isinstance(retryable_attr, bool):
        return retryable_attr
    if isinstance(exc, UpstreamStreamError):
        if status_code is None:
            return True
        if 500 <= status_code < 600:
            return True
        if status_code in (429, 408):
            return True
        return False
    return True


async def try_candidates_stream(
    *,
    candidates: Sequence[CandidateScore | PhysicalModel],
    client: httpx.AsyncClient,
    redis: Redis,
    db: DbSession,
    payload: dict[str, Any],
    logical_model_id: str,
    api_key: AuthenticatedAPIKey,
    on_first_chunk: Callable[[str, str], Awaitable[None]],
    api_style: str | None = None,
    on_stream_complete: Callable[[str], None] | None = None,
    on_failure: Callable[..., None] | None = None,
    messages_path_override: str | None = None,
    fallback_path_override: str | None = None,
    routing_state: RoutingStateService | None = None,
    request_id: str | None = None,
    attempts: list[dict[str, Any]] | None = None,
    outcome: dict[str, Any] | None = None,
) -> AsyncIterator[bytes]:
    from app.api.v1.chat.transport_handlers_stream import (
        execute_claude_cli_stream,
        execute_http_stream,
        execute_sdk_stream,
    )

    resolved_style = _resolve_api_style(payload, api_style)
    state = routing_state or RoutingStateService(redis=redis)

    last_status: int | None = None
    last_error_text: str | None = None
    last_provider_id: str | None = None
    skipped_count = 0

    for idx, upstream in enumerate(candidates):
        cand = _unwrap_candidate(upstream)
        provider_id = cand.provider_id
        model_id = cand.model_id
        base_endpoint = cand.endpoint
        upstream_api_style = getattr(cand, "api_style", "openai")
        is_last = idx == len(candidates) - 1

        cooldown = await state.get_failure_cooldown_status(provider_id)
        if cooldown.should_skip:
            skipped_count += 1
            if attempts is not None:
                attempts.append(
                    {
                        "idx": idx,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "transport": None,
                        "endpoint": base_endpoint,
                        "success": False,
                        "retryable": True,
                        "skipped": True,
                        "skip_reason": "failure_cooldown",
                        "status_code": None,
                        "error_category": "failure_cooldown",
                        "error_message": None,
                        "duration_ms": 0,
                        "cooldown": {
                            "count": cooldown.count,
                            "threshold": cooldown.threshold,
                            "cooldown_seconds": cooldown.cooldown_seconds,
                        },
                    }
                )
            logger.warning(
                "candidate_retry(stream): skipping provider %s (failures=%d/%d, cooldown=%ds)",
                provider_id,
                cooldown.count,
                cooldown.threshold,
                cooldown.cooldown_seconds,
            )
            continue

        provider_cfg = get_provider_config(provider_id)
        if provider_cfg is None:
            last_status = status.HTTP_503_SERVICE_UNAVAILABLE
            last_error_text = f"Provider '{provider_id}' is not configured"
            last_provider_id = provider_id
            if attempts is not None:
                attempts.append(
                    {
                        "idx": idx,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "transport": None,
                        "endpoint": base_endpoint,
                        "success": False,
                        "retryable": False,
                        "skipped": False,
                        "status_code": int(last_status),
                        "error_category": "provider_not_configured",
                        "error_message": extract_error_message(last_error_text),
                        "duration_ms": 0,
                    }
                )
            continue

        transport = getattr(provider_cfg, "transport", "http")
        attempt: dict[str, Any] | None = None
        start_attempt = time.perf_counter()
        if attempts is not None:
            attempt = {
                "idx": idx,
                "provider_id": provider_id,
                "model_id": model_id,
                "transport": str(transport),
                "endpoint": base_endpoint,
                "success": None,
                "retryable": None,
                "skipped": False,
                "status_code": None,
                "error_category": None,
                "error_message": None,
                "ttfb_ms": None,
                "duration_ms": None,
            }
            attempts.append(attempt)

        if transport == "claude_cli":
            iterator = execute_claude_cli_stream(
                client=client,
                redis=redis,
                db=db,
                provider_id=provider_id,
                model_id=model_id,
                payload=payload,
                logical_model_id=logical_model_id,
                api_style=resolved_style,
                api_key=api_key,
            )
        elif transport == "sdk":
            iterator = execute_sdk_stream(
                redis=redis,
                db=db,
                provider_id=provider_id,
                model_id=model_id,
                payload=payload,
                logical_model_id=logical_model_id,
                api_style=resolved_style,
                api_key=api_key,
            )
        else:
            iterator = execute_http_stream(
                client=client,
                redis=redis,
                db=db,
                provider_id=provider_id,
                model_id=model_id,
                url=base_endpoint,
                payload=payload,
                logical_model_id=logical_model_id,
                api_style=resolved_style,
                upstream_api_style=upstream_api_style,
                api_key=api_key,
                messages_path_override=messages_path_override,
                fallback_path_override=fallback_path_override,
            )

        first_chunk_seen = False
        try:
            async for chunk in iterator:
                if not first_chunk_seen:
                    first_chunk_seen = True
                    await state.clear_provider_failure(provider_id)
                    await on_first_chunk(provider_id, model_id)
                    if attempt is not None:
                        attempt["ttfb_ms"] = int(
                            max(0.0, (time.perf_counter() - start_attempt) * 1000)
                        )
                yield chunk

            if on_stream_complete is not None:
                on_stream_complete(provider_id)
            if attempt is not None:
                attempt.update(
                    {
                        "success": True,
                        "retryable": False,
                        "status_code": 200,
                        "duration_ms": int(
                            max(0.0, (time.perf_counter() - start_attempt) * 1000)
                        ),
                    }
                )
            if outcome is not None:
                outcome.update(
                    {
                        "success": True,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "status_code": 200,
                    }
                )
            return
        except Exception as exc:
            error_status = getattr(exc, "status_code", None)
            error_text = str(exc)
            last_status = error_status
            last_error_text = error_text
            last_provider_id = provider_id

            retryable = _is_stream_error_retryable(exc, error_status)
            penalize = bool(getattr(exc, "penalize", True))
            if penalize:
                _call_failure_hook(on_failure, provider_id, bool(retryable))

            if penalize and retryable and error_status in (500, 502, 503, 504, 429):
                await state.increment_provider_failure(provider_id)

            if retryable and not is_last:
                if attempt is not None:
                    attempt.update(
                        {
                            "success": False,
                            "retryable": True,
                            "status_code": error_status,
                            "error_category": str(getattr(exc, "error_category", "") or "") or None,
                            "error_message": extract_error_message(error_text)[:2000],
                            "duration_ms": int(
                                max(0.0, (time.perf_counter() - start_attempt) * 1000)
                            ),
                        }
                    )
                continue

            message = extract_error_message(error_text)
            if attempt is not None:
                attempt.update(
                    {
                        "success": False,
                        "retryable": bool(retryable),
                        "status_code": error_status,
                        "error_category": str(getattr(exc, "error_category", "") or "") or None,
                        "error_message": message[:2000],
                        "duration_ms": int(
                            max(0.0, (time.perf_counter() - start_attempt) * 1000)
                        ),
                    }
                )
            if outcome is not None:
                outcome.update(
                    {
                        "success": False,
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "status_code": 200,
                        "upstream_status": error_status,
                        "error_message": message[:2000],
                    }
                )
            error_payload = {
                "error": {
                    "type": "upstream_error",
                    "status": error_status,
                    "message": message,
                    "provider_id": provider_id,
                    "request_id": request_id,
                }
            }
            error_chunk = f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode()
            yield error_chunk
            return

    message = f"All upstream providers failed for logical model '{logical_model_id}'"
    details: list[str] = []
    if skipped_count:
        details.append(f"skipped={skipped_count} (in failure cooldown)")
    if last_provider_id:
        details.append(f"last_provider={last_provider_id}")
    if last_status is not None:
        details.append(f"last_status={last_status}")
    if last_error_text:
        details.append(f"last_error={extract_error_message(last_error_text)}")
    detail_text = message if not details else f"{message}; " + ", ".join(details)
    if outcome is not None:
        outcome.update(
            {
                "success": False,
                "provider_id": last_provider_id,
                "status_code": 200,
                "upstream_status": last_status,
                "error_message": extract_error_message(last_error_text)[:2000] if last_error_text else None,
            }
        )
    error_payload = {
        "error": {"type": "all_providers_failed", "message": detail_text, "request_id": request_id}
    }
    error_chunk = f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode()
    yield error_chunk


__all__ = [
    "try_candidates_non_stream",
    "try_candidates_stream",
]
