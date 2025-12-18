"""
重构后的聊天路由（v1）

目标：保留旧版行为与能力（多风格请求、动态模型发现、粘性会话、健康检查、失败冷却、计费/审核），
同时把 route 层收敛为“参数解析 + 认证/权限/积分校验 + 调用 handler”。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺少 redis 时的兜底类型
    Redis = object  # type: ignore[misc,assignment]

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_db, get_http_client, get_redis
from app.errors import forbidden
from app.logging_config import logger
from app.log_sanitizer import sanitize_headers_for_log
from app.services.client_app_fingerprint import infer_client_app_name
from app.services.chat_routing_service import (
    _normalize_payload_by_model,
    _strip_model_group_prefix,
)
from app.services.credit_service import (
    InsufficientCreditsError,
    ensure_account_usable,
)
from app.services.user_app_metrics_service import record_user_app_request_metric
from app.services.user_provider_service import get_accessible_provider_ids
from app.settings import settings
from app.upstream import detect_request_format

from app.api.v1.chat.middleware import (
    enforce_request_moderation,
    wrap_stream_with_moderation,
)
from app.api.v1.chat.request_handler import RequestHandler

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: DbSession = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    raw_body: dict[str, Any] = Body(...),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    logger.info(
        "chat: incoming model=%r stream=%r user=%s session=%s",
        raw_body.get("model"),
        raw_body.get("stream"),
        current_key.user_id,
        x_session_id,
    )

    # 入口请求口径的 App 使用指标：用来回答“某用户主要用哪些客户端调用网关”。
    record_user_app_request_metric(
        db,
        user_id=current_key.user_id,
        api_key_id=current_key.id,
        app_name=infer_client_app_name(request.headers),
    )

    payload = dict(raw_body)
    api_style_override = payload.pop("_apiproxy_api_style", None)
    skip_normalization = bool(payload.pop("_apiproxy_skip_normalize", False))
    messages_path_override = payload.pop("_apiproxy_messages_path", None)
    fallback_path_override = payload.pop("_apiproxy_fallback_path", "/v1/chat/completions")

    if not skip_normalization:
        payload = _normalize_payload_by_model(payload)

    accept_header = request.headers.get("accept", "")
    wants_event_stream = "text/event-stream" in accept_header.lower()
    payload_stream_raw = payload.get("stream", None)

    if payload_stream_raw is False:
        stream = False
    else:
        stream = bool(payload_stream_raw) or wants_event_stream

    if stream and payload_stream_raw is None:
        payload["stream"] = True

    billing_request_id = uuid.uuid4().hex
    billing_final_key = f"chat:{billing_request_id}:final"
    billing_precharge_key = f"chat:{billing_request_id}:precharge"

    api_style = api_style_override or detect_request_format(payload)
    requested_model = payload.get("model")
    normalized_model = _strip_model_group_prefix(requested_model)
    lookup_model_id = normalized_model or requested_model
    if not isinstance(lookup_model_id, str) or not lookup_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "model 字段不能为空"},
        )

    logger.info(
        "chat: resolved api_style=%s lookup_model_id=%r stream=%s",
        api_style,
        lookup_model_id,
        stream,
    )

    enforce_request_moderation(
        payload,
        session_id=x_session_id,
        api_key=current_key,
        logical_model=lookup_model_id,
    )

    try:
        ensure_account_usable(db, user_id=current_key.user_id)
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "CREDIT_NOT_ENOUGH",
                "message": str(exc),
                "balance": exc.balance,
            },
        )

    accessible_provider_ids = get_accessible_provider_ids(db, current_key.user_id)
    if not accessible_provider_ids:
        raise forbidden("当前用户暂无可用的提供商")

    effective_provider_ids = set(accessible_provider_ids)
    if current_key.has_provider_restrictions:
        allowed = {pid for pid in current_key.allowed_provider_ids if pid}
        effective_provider_ids &= allowed
        if not effective_provider_ids:
            raise forbidden(
                "当前 API Key 未允许访问任何可用的提供商",
                details={
                    "api_key_id": str(current_key.id),
                    "allowed_provider_ids": current_key.allowed_provider_ids,
                },
            )

    handler = RequestHandler(
        api_key=current_key,
        db=db,
        redis=redis,
        client=client,
    )

    try:
        if not stream:
            return await handler.handle(
                payload=payload,
                requested_model=requested_model,
                lookup_model_id=lookup_model_id,
                api_style=api_style,
                effective_provider_ids=effective_provider_ids,
                session_id=x_session_id,
                idempotency_key=billing_final_key,
                messages_path_override=messages_path_override,
                fallback_path_override=fallback_path_override,
            )

        # 关键点：流式响应一旦开始发送 headers，后续在生成器里抛出的 HTTPException
        # 将无法走 FastAPI 的异常处理流程，只会在服务端日志里表现为 TaskGroup/ExceptionGroup。
        # 因此把“可预判的选择/发现错误”（如模型不可用）前置到构建 StreamingResponse 之前。
        selection = await handler.provider_selector.select(
            requested_model=requested_model,
            lookup_model_id=lookup_model_id,
            api_style=api_style,
            effective_provider_ids=effective_provider_ids,
            session_id=x_session_id,
            user_id=uuid.UUID(str(current_key.user_id)),
            is_superuser=bool(current_key.is_superuser),
        )

        provider_holder: dict[str, str | None] = {"provider_id": None}

        def _set_provider(provider_id: str) -> None:
            provider_holder["provider_id"] = provider_id

        async def stream_generator():
            async for chunk in handler.handle_stream(
                payload=payload,
                requested_model=requested_model,
                lookup_model_id=lookup_model_id,
                api_style=api_style,
                effective_provider_ids=effective_provider_ids,
                selection=selection,
                session_id=x_session_id,
                idempotency_key=billing_precharge_key,
                messages_path_override=messages_path_override,
                fallback_path_override=fallback_path_override,
                provider_id_sink=_set_provider,
            ):
                yield chunk

        return StreamingResponse(
            wrap_stream_with_moderation(
                stream_generator(),
                session_id=x_session_id,
                api_key=current_key,
                logical_model=lookup_model_id,
                provider_id=None,
                provider_id_getter=lambda: provider_holder.get("provider_id"),
            ),
            media_type="text/event-stream",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "chat: request failed user=%s model=%s error=%s",
            current_key.user_id,
            lookup_model_id,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(exc)}",
        )


@router.post("/v1/responses")
async def responses_endpoint(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: DbSession = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    raw_body: dict[str, Any] = Body(...),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    OpenAI Responses API 兼容端点（重构版）。
    """
    passthrough_payload = dict(raw_body)
    passthrough_payload["_apiproxy_api_style"] = "responses"
    passthrough_payload["_apiproxy_skip_normalize"] = True

    return await chat_completions(
        request=request,
        client=client,
        redis=redis,
        db=db,
        x_session_id=x_session_id,
        raw_body=passthrough_payload,
        current_key=current_key,
    )


@router.post("/v1/messages")
async def claude_messages_endpoint(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: DbSession = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    raw_body: dict[str, Any] = Body(...),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    Claude/Anthropic Messages API 兼容端点（重构版）。
    """
    if settings.environment.lower() == "development":
        logger.info("=" * 80)
        logger.info("Claude Messages API 请求详情 (/v1/messages)")
        logger.info("=" * 80)
        logger.info("请求头:")
        sanitized_headers = sanitize_headers_for_log(request.headers)
        for header_name, header_value in sanitized_headers.items():
            logger.info("  %s: %s", header_name, header_value)
        logger.info("请求体:")
        logger.info(json.dumps(raw_body, indent=2, ensure_ascii=False))
        logger.info("=" * 80)

    forward_body = dict(raw_body)
    forward_body["_apiproxy_api_style"] = "claude"
    forward_body["_apiproxy_skip_normalize"] = True
    forward_body["_apiproxy_fallback_path"] = "/v1/chat/completions"

    return await chat_completions(
        request=request,
        client=client,
        redis=redis,
        db=db,
        x_session_id=x_session_id,
        raw_body=forward_body,
        current_key=current_key,
    )


__all__ = ["router"]
