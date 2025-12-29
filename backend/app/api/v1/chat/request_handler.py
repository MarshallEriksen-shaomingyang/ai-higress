"""
请求处理协调器（v2）

职责边界：
- Resolve/Decide 交由 ProviderSelector（加载/构建 LogicalModel + 调度排序）
- Execute 交由 candidate_retry（按候选顺序执行、失败重试、实时故障标记）
- Route 层负责：参数解析、内容审核、积分校验、用户/Key 权限计算、最终返回 StreamingResponse
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.v1.chat.billing import record_completion_usage, record_stream_usage
from app.api.v1.chat.candidate_retry import try_candidates_non_stream, try_candidates_stream
from app.api.v1.chat.middleware import apply_response_moderation
from app.api.v1.chat.provider_selector import ProviderSelectionResult, ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.api.v1.chat.upstream_error_classifier import extract_error_message
from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.models import Provider
from app.services.metrics_service import record_provider_token_usage
from app.services.request_log_service import append_request_log, build_request_log_entry
from app.settings import settings


def _extract_last_user_text(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    msgs = payload.get("messages")
    if not isinstance(msgs, list):
        return ""
    for item in reversed(msgs):
        if isinstance(item, dict) and item.get("role") == "user":
            val = item.get("content")
            if isinstance(val, str):
                return val
    return ""


def _safe_uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except Exception:
        return None


class RequestHandler:
    """
    执行阶段协调器：负责把“已排序的候选 upstream”转成最终响应，并补齐
    Session 绑定、动态权重记录、计费、非流式响应审核。
    """

    def __init__(
        self,
        *,
        api_key: AuthenticatedAPIKey,
        db: DbSession,
        redis: Redis,
        client: httpx.AsyncClient,
    ):
        self.api_key = api_key
        self.db = db
        self.redis = redis
        self.client = client

        self.routing_state = RoutingStateService(redis=redis)
        self.provider_selector = ProviderSelector(
            client=client, redis=redis, db=db, routing_state=self.routing_state
        )

    async def handle(
        self,
        *,
        payload: dict[str, Any],
        requested_model: Any,
        lookup_model_id: str,
        api_style: str,
        effective_provider_ids: set[str],
        request_id: str | None = None,
        log_request: bool = False,
        request_method: str | None = None,
        request_path: str | None = None,
        idempotency_key: str | None = None,
        assistant_id: UUID | None = None,
        messages_path_override: str | None = None,
        fallback_path_override: str | None = None,
        provider_id_sink: Callable[[str, str], None] | None = None,
        billing_reason: str | None = None,
    ) -> JSONResponse:
        start = time.perf_counter()
        attempts: list[dict[str, Any]] = []
        outcome: dict[str, Any] = {}
        logger.info(
            "chat_v2: handle non-stream user=%s logical_model=%s api_style=%s",
            self.api_key.user_id,
            lookup_model_id,
            api_style,
        )

        user_uuid = _safe_uuid(self.api_key.user_id)
        api_key_uuid = _safe_uuid(self.api_key.id)

        selection = await self.provider_selector.select(
            requested_model=requested_model,
            lookup_model_id=lookup_model_id,
            api_style=api_style,
            effective_provider_ids=effective_provider_ids,
            user_id=user_uuid,
            is_superuser=bool(self.api_key.is_superuser),
            bandit_project_id=api_key_uuid,
            bandit_assistant_id=assistant_id,
            bandit_user_text=_extract_last_user_text(payload),
            bandit_request_payload=payload,
        )

        selected_provider_id: str | None = None
        selected_model_id: str | None = None
        base_weights = selection.base_weights

        async def on_success(provider_id: str, model_id: str) -> None:
            nonlocal selected_provider_id, selected_model_id
            selected_provider_id = provider_id
            selected_model_id = model_id
            if provider_id_sink is not None:
                try:
                    provider_id_sink(provider_id, model_id)
                except Exception:  # pragma: no cover
                    logger.debug("chat_v2: provider_id_sink failed", exc_info=True)

            self.routing_state.record_success(
                lookup_model_id, provider_id, base_weights.get(provider_id, 1.0)
            )

        def on_failure(provider_id: str, *, retryable: bool) -> None:
            self.routing_state.record_failure(
                lookup_model_id,
                provider_id,
                base_weights.get(provider_id, 1.0),
                retryable=retryable,
            )

        try:
            upstream_response = await try_candidates_non_stream(
                candidates=selection.ordered_candidates,
                client=self.client,
                redis=self.redis,
                db=self.db,
                payload=payload,
                logical_model_id=lookup_model_id,
                api_style=api_style,
                api_key=self.api_key,
                on_success=on_success,
                on_failure=on_failure,
                messages_path_override=messages_path_override,
                fallback_path_override=fallback_path_override,
                routing_state=self.routing_state,
                request_id=request_id,
                attempts=attempts,
                outcome=outcome,
            )
        except HTTPException as exc:
            if log_request:
                await append_request_log(
                    self.redis,
                    user_id=str(self.api_key.user_id),
                    entry=build_request_log_entry(
                        request_id=str(request_id or ""),
                        user_id=str(self.api_key.user_id),
                        api_key_id=str(self.api_key.id),
                        method=request_method,
                        path=request_path,
                        logical_model=lookup_model_id,
                        requested_model=str(requested_model) if requested_model is not None else None,
                        api_style=api_style,
                        is_stream=False,
                        status_code=int(exc.status_code),
                        latency_ms=int(max(0.0, (time.perf_counter() - start) * 1000)),
                        selected_provider_id=outcome.get("provider_id") or selected_provider_id,
                        selected_provider_model=outcome.get("model_id") or selected_model_id,
                        upstream_status=outcome.get("upstream_status"),
                        error_message=extract_error_message(getattr(exc, "detail", None)),
                        attempts=attempts,
                    ),
                )
            raise

        raw_text = upstream_response.body.decode("utf-8", errors="ignore")
        response_payload: dict[str, Any] | None = None
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                response_payload = parsed
        except Exception:
            response_payload = None

        # 非流式响应审核（可能抛出 400）
        try:
            moderated = apply_response_moderation(
                response_payload if response_payload is not None else {"raw": raw_text},
                session_id=None,
                api_key=self.api_key,
                logical_model=lookup_model_id,
                provider_id=selected_provider_id,
                status_code=upstream_response.status_code,
            )
        except HTTPException as exc:
            if log_request:
                await append_request_log(
                    self.redis,
                    user_id=str(self.api_key.user_id),
                    entry=build_request_log_entry(
                        request_id=str(request_id or ""),
                        user_id=str(self.api_key.user_id),
                        api_key_id=str(self.api_key.id),
                        method=request_method,
                        path=request_path,
                        logical_model=lookup_model_id,
                        requested_model=str(requested_model) if requested_model is not None else None,
                        api_style=api_style,
                        is_stream=False,
                        status_code=int(exc.status_code),
                        latency_ms=int(max(0.0, (time.perf_counter() - start) * 1000)),
                        selected_provider_id=selected_provider_id,
                        selected_provider_model=selected_model_id,
                        upstream_status=upstream_response.status_code,
                        error_message=extract_error_message(getattr(exc, "detail", None)),
                        attempts=attempts,
                    ),
                )
            raise

        # 计费：使用上游原始 payload 提取 usage（避免审核脱敏影响 usage 字段）
        try:
            if user_uuid is not None and api_key_uuid is not None:
                record_completion_usage(
                    self.db,
                    user_id=user_uuid,
                    api_key_id=api_key_uuid,
                    logical_model_name=lookup_model_id,
                    provider_id=selected_provider_id,
                    provider_model_id=selected_model_id,
                    response_payload=response_payload,
                    request_payload=payload,
                    is_stream=False,
                    reason=billing_reason,
                    idempotency_key=idempotency_key,
                )
        except Exception:  # pragma: no cover
            logger.exception(
                "chat_v2: failed to record non-stream credit usage user=%s model=%s",
                self.api_key.user_id,
                lookup_model_id,
            )

        if log_request:
            await append_request_log(
                self.redis,
                user_id=str(self.api_key.user_id),
                entry=build_request_log_entry(
                    request_id=str(request_id or ""),
                    user_id=str(self.api_key.user_id),
                    api_key_id=str(self.api_key.id),
                    method=request_method,
                    path=request_path,
                    logical_model=lookup_model_id,
                    requested_model=str(requested_model) if requested_model is not None else None,
                    api_style=api_style,
                    is_stream=False,
                    status_code=int(upstream_response.status_code),
                    latency_ms=int(max(0.0, (time.perf_counter() - start) * 1000)),
                    selected_provider_id=selected_provider_id,
                    selected_provider_model=selected_model_id,
                    upstream_status=int(upstream_response.status_code),
                    error_message=None,
                    attempts=attempts,
                ),
            )

        return JSONResponse(content=moderated, status_code=upstream_response.status_code)

    async def handle_stream(
        self,
        *,
        payload: dict[str, Any],
        requested_model: Any,
        lookup_model_id: str,
        api_style: str,
        effective_provider_ids: set[str],
        selection: ProviderSelectionResult | None = None,
        request_id: str | None = None,
        log_request: bool = False,
        request_method: str | None = None,
        request_path: str | None = None,
        idempotency_key: str | None = None,
        assistant_id: UUID | None = None,
        messages_path_override: str | None = None,
        fallback_path_override: str | None = None,
        provider_id_sink: Callable[..., None] | None = None,
    ) -> AsyncIterator[bytes]:
        start = time.perf_counter()
        attempts: list[dict[str, Any]] = []
        outcome: dict[str, Any] = {}
        logger.info(
            "chat_v2: handle stream user=%s logical_model=%s api_style=%s",
            self.api_key.user_id,
            lookup_model_id,
            api_style,
        )

        user_uuid = _safe_uuid(self.api_key.user_id)
        api_key_uuid = _safe_uuid(self.api_key.id)

        if selection is None:
            selection = await self.provider_selector.select(
                requested_model=requested_model,
                lookup_model_id=lookup_model_id,
                api_style=api_style,
                effective_provider_ids=effective_provider_ids,
                user_id=user_uuid,
                is_superuser=bool(self.api_key.is_superuser),
                bandit_project_id=api_key_uuid,
                bandit_assistant_id=assistant_id,
                bandit_user_text=_extract_last_user_text(payload),
                bandit_request_payload=payload,
            )

        # 预扣费：尽量使用首选候选 provider/model（与 v1 行为对齐）
        try:
            primary_provider_id: str | None = None
            primary_model_id: str | None = None
            if selection.ordered_candidates:
                primary = selection.ordered_candidates[0].upstream
                primary_provider_id = primary.provider_id
                primary_model_id = primary.model_id
            if user_uuid is not None and api_key_uuid is not None:
                record_stream_usage(
                    self.db,
                    user_id=user_uuid,
                    api_key_id=api_key_uuid,
                    logical_model_name=lookup_model_id,
                    provider_id=primary_provider_id,
                    provider_model_id=primary_model_id,
                    payload=payload,
                    idempotency_key=idempotency_key,
                )
        except Exception:  # pragma: no cover
            logger.exception(
                "chat_v2: failed to record streaming credit usage user=%s model=%s",
                self.api_key.user_id,
                lookup_model_id,
            )

        base_weights = selection.base_weights
        selected_provider_id: str | None = None
        token_estimated = False

        async def on_first_chunk(provider_id: str, model_id: str) -> None:
            nonlocal selected_provider_id, token_estimated
            selected_provider_id = provider_id
            if provider_id_sink is not None:
                try:
                    provider_id_sink(provider_id, model_id)
                except TypeError:
                    provider_id_sink(provider_id)

            if token_estimated:
                return

            approx_tokens: int | None = None
            for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
                value = payload.get(key)
                if isinstance(value, int) and value > 0:
                    approx_tokens = value
                    break

            if approx_tokens is None:
                approx_tokens = int(getattr(settings, "streaming_min_tokens", 0) or 0)

            if approx_tokens <= 0:
                return

            try:
                transport = (
                    self.db.execute(
                        select(Provider.transport).where(Provider.provider_id == provider_id)
                    )
                    .scalars()
                    .first()
                )
                transport_str = str(transport or "http")
            except Exception:  # pragma: no cover
                transport_str = "http"

            try:
                record_provider_token_usage(
                    self.db,
                    provider_id=provider_id,
                    logical_model=lookup_model_id,
                    transport=transport_str,
                    is_stream=True,
                    user_id=user_uuid,
                    api_key_id=api_key_uuid,
                    occurred_at=dt.datetime.now(tz=dt.UTC),
                    input_tokens=None,
                    output_tokens=None,
                    total_tokens=approx_tokens,
                    estimated=True,
                )
            except Exception:  # pragma: no cover
                logger.exception(
                    "chat_v2: failed to record streaming token usage user=%s model=%s provider=%s",
                    self.api_key.user_id,
                    lookup_model_id,
                    provider_id,
                )
            token_estimated = True

        def on_stream_complete(provider_id: str) -> None:
            self.routing_state.record_success(
                lookup_model_id, provider_id, base_weights.get(provider_id, 1.0)
            )

        def on_failure(provider_id: str, *, retryable: bool) -> None:
            self.routing_state.record_failure(
                lookup_model_id,
                provider_id,
                base_weights.get(provider_id, 1.0),
                retryable=retryable,
            )

        try:
            async for chunk in try_candidates_stream(
                candidates=selection.ordered_candidates,
                client=self.client,
                redis=self.redis,
                db=self.db,
                payload=payload,
                logical_model_id=lookup_model_id,
                api_style=api_style,
                api_key=self.api_key,
                on_first_chunk=on_first_chunk,
                on_stream_complete=on_stream_complete,
                on_failure=on_failure,
                messages_path_override=messages_path_override,
                fallback_path_override=fallback_path_override,
                routing_state=self.routing_state,
                request_id=request_id,
                attempts=attempts,
                outcome=outcome,
            ):
                yield chunk
        finally:
            if log_request:
                success = bool(outcome.get("success"))
                await append_request_log(
                    self.redis,
                    user_id=str(self.api_key.user_id),
                    entry=build_request_log_entry(
                        request_id=str(request_id or ""),
                        user_id=str(self.api_key.user_id),
                        api_key_id=str(self.api_key.id),
                        method=request_method,
                        path=request_path,
                        logical_model=lookup_model_id,
                        requested_model=str(requested_model) if requested_model is not None else None,
                        api_style=api_style,
                        is_stream=True,
                        status_code=200,
                        latency_ms=int(max(0.0, (time.perf_counter() - start) * 1000)),
                        selected_provider_id=outcome.get("provider_id"),
                        selected_provider_model=outcome.get("model_id"),
                        upstream_status=outcome.get("upstream_status"),
                        error_message=None if success else outcome.get("error_message"),
                        attempts=attempts,
                    ),
                )


__all__ = ["RequestHandler"]
