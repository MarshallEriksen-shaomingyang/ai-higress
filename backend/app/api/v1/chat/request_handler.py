"""
请求处理协调器（v2）

职责边界：
- Resolve/Decide 交由 ProviderSelector（加载/构建 LogicalModel + 调度排序）
- Execute 交由 candidate_retry（按候选顺序执行、失败重试、实时故障标记）
- Route 层负责：参数解析、内容审核、积分校验、用户/Key 权限计算、最终返回 StreamingResponse
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

import httpx
from fastapi.responses import JSONResponse

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from sqlalchemy.orm import Session as DbSession

from app.api.v1.chat.billing import record_completion_usage, record_stream_usage
from app.api.v1.chat.candidate_retry import try_candidates_non_stream, try_candidates_stream
from app.api.v1.chat.middleware import apply_response_moderation
from app.api.v1.chat.provider_selector import ProviderSelectionResult, ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.api.v1.chat.session_manager import SessionManager
from app.auth import AuthenticatedAPIKey
from app.logging_config import logger


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
        self.session_manager = SessionManager(redis=redis)

    async def handle(
        self,
        *,
        payload: dict[str, Any],
        requested_model: Any,
        lookup_model_id: str,
        api_style: str,
        effective_provider_ids: set[str],
        session_id: str | None = None,
        idempotency_key: str | None = None,
        messages_path_override: str | None = None,
        fallback_path_override: str | None = None,
    ) -> JSONResponse:
        logger.info(
            "chat_v2: handle non-stream user=%s logical_model=%s api_style=%s session_id=%s",
            self.api_key.user_id,
            lookup_model_id,
            api_style,
            session_id,
        )

        selection = await self.provider_selector.select(
            requested_model=requested_model,
            lookup_model_id=lookup_model_id,
            api_style=api_style,
            effective_provider_ids=effective_provider_ids,
            session_id=session_id,
            user_id=UUID(str(self.api_key.user_id)),
            is_superuser=bool(self.api_key.is_superuser),
        )

        selected_provider_id: str | None = None
        selected_model_id: str | None = None
        base_weights = selection.base_weights

        async def on_success(provider_id: str, model_id: str) -> None:
            nonlocal selected_provider_id, selected_model_id
            selected_provider_id = provider_id
            selected_model_id = model_id

            self.routing_state.record_success(
                lookup_model_id, provider_id, base_weights.get(provider_id, 1.0)
            )
            if session_id:
                await self.session_manager.bind_session(
                    session_id=session_id,
                    logical_model_id=lookup_model_id,
                    provider_id=provider_id,
                    model_id=model_id,
                )

        def on_failure(provider_id: str, *, retryable: bool) -> None:
            self.routing_state.record_failure(
                lookup_model_id,
                provider_id,
                base_weights.get(provider_id, 1.0),
                retryable=retryable,
            )

        upstream_response = await try_candidates_non_stream(
            candidates=selection.ordered_candidates,
            client=self.client,
            redis=self.redis,
            db=self.db,
            payload=payload,
            logical_model_id=lookup_model_id,
            api_style=api_style,
            api_key=self.api_key,
            session_id=session_id,
            on_success=on_success,
            on_failure=on_failure,
            messages_path_override=messages_path_override,
            fallback_path_override=fallback_path_override,
            routing_state=self.routing_state,
        )

        raw_text = upstream_response.body.decode("utf-8", errors="ignore")
        response_payload: dict[str, Any] | None = None
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                response_payload = parsed
        except Exception:
            response_payload = None

        # 非流式响应审核（可能抛出 400）
        moderated = apply_response_moderation(
            response_payload if response_payload is not None else {"raw": raw_text},
            session_id=session_id,
            api_key=self.api_key,
            logical_model=lookup_model_id,
            provider_id=selected_provider_id,
            status_code=upstream_response.status_code,
        )

        # 计费：使用上游原始 payload 提取 usage（避免审核脱敏影响 usage 字段）
        record_completion_usage(
            self.db,
            user_id=UUID(str(self.api_key.user_id)),
            api_key_id=UUID(str(self.api_key.id)),
            logical_model_name=lookup_model_id,
            provider_id=selected_provider_id,
            provider_model_id=selected_model_id,
            response_payload=response_payload,
            request_payload=payload,
            is_stream=False,
            idempotency_key=idempotency_key,
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
        session_id: str | None = None,
        idempotency_key: str | None = None,
        messages_path_override: str | None = None,
        fallback_path_override: str | None = None,
        provider_id_sink: Callable[[str], None] | None = None,
    ) -> AsyncIterator[bytes]:
        logger.info(
            "chat_v2: handle stream user=%s logical_model=%s api_style=%s session_id=%s",
            self.api_key.user_id,
            lookup_model_id,
            api_style,
            session_id,
        )

        if selection is None:
            selection = await self.provider_selector.select(
                requested_model=requested_model,
                lookup_model_id=lookup_model_id,
                api_style=api_style,
                effective_provider_ids=effective_provider_ids,
                session_id=session_id,
                user_id=UUID(str(self.api_key.user_id)),
                is_superuser=bool(self.api_key.is_superuser),
            )

        # 预扣费：尽量使用首选候选 provider/model（与 v1 行为对齐）
        try:
            primary_provider_id: str | None = None
            primary_model_id: str | None = None
            if selection.ordered_candidates:
                primary = selection.ordered_candidates[0].upstream
                primary_provider_id = primary.provider_id
                primary_model_id = primary.model_id
            record_stream_usage(
                self.db,
                user_id=UUID(str(self.api_key.user_id)),
                api_key_id=UUID(str(self.api_key.id)),
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

        async def on_first_chunk(provider_id: str, model_id: str) -> None:
            nonlocal selected_provider_id
            selected_provider_id = provider_id
            if provider_id_sink is not None:
                provider_id_sink(provider_id)
            if session_id:
                await self.session_manager.bind_session(
                    session_id=session_id,
                    logical_model_id=lookup_model_id,
                    provider_id=provider_id,
                    model_id=model_id,
                )

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

        async for chunk in try_candidates_stream(
            candidates=selection.ordered_candidates,
            client=self.client,
            redis=self.redis,
            db=self.db,
            payload=payload,
            logical_model_id=lookup_model_id,
            api_style=api_style,
            api_key=self.api_key,
            session_id=session_id,
            on_first_chunk=on_first_chunk,
            on_stream_complete=on_stream_complete,
            on_failure=on_failure,
            messages_path_override=messages_path_override,
            fallback_path_override=fallback_path_override,
            routing_state=self.routing_state,
        ):
            yield chunk


__all__ = ["RequestHandler"]
