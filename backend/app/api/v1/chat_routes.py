"""
聊天相关网关路由：
- POST /v1/chat/completions
- POST /v1/responses
- POST /v1/messages

从 app.routes 中抽离出来，保持路由行为不变，同时让 routes.py 更精简。
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session as DbSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺少 redis 时的兜底类型
    Redis = object  # type: ignore[misc,assignment]

from app.auth import AuthenticatedAPIKey, require_api_key
from app.context_store import save_context
from app.deps import get_db, get_http_client, get_redis
from app.errors import forbidden
from app.logging_config import logger
from app.provider.config import get_provider_config
from app.provider.key_pool import (
    NoAvailableProviderKey,
    SelectedProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)
from app.provider.sdk_selector import get_sdk_driver, normalize_base_url
from app.routing.exceptions import NoAllowedProvidersAvailable
from app.routing.mapper import select_candidate_upstreams
from app.routing.provider_weight import (
    load_dynamic_weights,
    record_provider_failure,
    record_provider_success,
)
from app.routing.scheduler import CandidateScore, choose_upstream
from app.routing.session_manager import bind_session, get_session
from app.schemas import (
    LogicalModel,
    PhysicalModel,
    RoutingMetrics,
    SchedulingStrategy,
    Session as RoutingSession,
)
from app.services.credit_service import (
    InsufficientCreditsError,
    ensure_account_usable,
    record_chat_completion_usage,
    record_streaming_request,
)
from app.services.metrics_service import (
    call_upstream_http_with_metrics,
    call_sdk_generate_with_metrics,
    stream_sdk_with_metrics,
    stream_upstream_with_metrics,
)
from app.storage.redis_service import get_logical_model
from app.upstream import UpstreamStreamError, detect_request_format

from app.services.chat_routing_service import *  # noqa: F401,F403

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
    """
    Gateway endpoint that accepts both OpenAI-style and Claude-style payloads.
    It auto-detects the format and whether the client expects a
    streaming response.

    When a logical model with the same name as `payload.model`
    exists in Redis, this endpoint routes via the multi-provider
    scheduler and performs weighted load balancing across upstream
    providers.
    """
    # Log a concise summary of the raw payload instead of the full body to reduce log noise.
    logger.info(
        "chat_completions: incoming_raw_body summary model=%r stream=%r keys=%s",
        raw_body.get("model"),
        raw_body.get("stream"),
        list(raw_body.keys()),
    )

    payload = dict(raw_body)  # shallow copy
    api_style_override = payload.pop("_apiproxy_api_style", None)
    skip_normalization = bool(payload.pop("_apiproxy_skip_normalize", False))
    messages_path_override = payload.pop("_apiproxy_messages_path", None)
    fallback_path_override = payload.pop("_apiproxy_fallback_path", "/v1/chat/completions")

    # First normalize payload based on model/provider conventions
    # (e.g. Gemini-style `input` -> OpenAI-style `messages`).
    if not skip_normalization:
        payload = _normalize_payload_by_model(payload)

    # 自动感应是否需要流式：
    # 1. 显式 payload.stream = True
    # 2. Accept 头包含 text/event-stream
    accept_header = request.headers.get("accept", "")
    wants_event_stream = "text/event-stream" in accept_header.lower()
    payload_stream_raw = payload.get("stream", None)

    if payload_stream_raw is False:
        # 客户端显式关闭流式
        stream = False
    else:
        stream = bool(payload_stream_raw) or wants_event_stream

    # 如果通过 Accept 头推断为流式，而 payload 里没带 stream 字段，则自动补上
    if stream and payload_stream_raw is None:
        payload["stream"] = True

    api_style = api_style_override or detect_request_format(payload)
    requested_model = payload.get("model")
    normalized_model = _strip_model_group_prefix(requested_model)
    lookup_model_id = normalized_model or requested_model

    logger.info(
        "chat_completions: resolved api_style=%s lookup_model_id=%r "
        "stream=%s x_session_id=%r",
        api_style,
        lookup_model_id,
        stream,
        x_session_id,
    )

    # 在路由和上游调用之前先做积分账户校验，避免在余额不足时仍然消耗上游配额。
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

    # Try multi-provider logical-model routing first. When a LogicalModel
    # named `lookup_model_id` exists in Redis, we use the routing
    # scheduler to pick a concrete upstream provider+model.
    logical_model: LogicalModel | None = None
    if isinstance(lookup_model_id, str):
        try:
            logical_model = await get_logical_model(redis, lookup_model_id)
            if logical_model is not None:
                logger.info(
                    "chat_completions: using static logical_model=%s "
                    "from Redis with %d upstreams",
                    logical_model.logical_id,
                    len(logical_model.upstreams),
                )
        except Exception:
            # Log and fall back to dynamic mapping; do not fail the request.
            logger.exception(
                "Failed to load logical model '%s' for routing", lookup_model_id
            )
            logical_model = None

    if logical_model is None:
        # Build a transient logical model based on provider /models
        # catalogues. This allows us to:
        # - verify the requested model exists in at least one provider;
        # - group providers that expose the same underlying model (e.g.
        #   "provider-2/xxx" and "provider-3/xxx") into a single logical
        #   model for cross-provider load-balancing; and
        # - reuse the scheduler + session stickiness logic without
        #   requiring manual LogicalModel configuration for every model id.
        logical_model = await _build_dynamic_logical_model_for_group(
            client=client,
            redis=redis,
            requested_model=requested_model,
            lookup_model_id=lookup_model_id,
            api_style=api_style,
        )

        if logical_model is not None:
            logger.info(
                "chat_completions: built dynamic logical_model=%s "
                "with %d upstreams",
                logical_model.logical_id,
                len(logical_model.upstreams),
            )

    if logical_model is None:
        # Either no providers are configured or none of them advertise
        # this model in their /models list; reject at the gateway.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": (
                    f"Requested model '{requested_model}' is not available "
                    "in any configured provider"
                )
            },
        )

    if logical_model is not None:
        # 1) Select candidate upstreams for this logical model.
        candidates: list[PhysicalModel] = select_candidate_upstreams(
            logical_model,
            preferred_region=None,
            exclude_providers=[],
        )
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"No upstreams available for logical model "
                    f"'{logical_model.logical_id}'"
                ),
            )

        try:
            candidates = _enforce_allowed_providers(candidates, current_key)
        except NoAllowedProvidersAvailable:
            raise forbidden(
                "当前 API Key 未允许访问任何可用的提供商",
                details={
                    "api_key_id": str(current_key.id),
                    "allowed_provider_ids": current_key.allowed_provider_ids,
                    "logical_model": logical_model.logical_id,
                },
            )

        # 2) Optional session stickiness using X-Session-Id as conversation id.
        session_obj: RoutingSession | None = None
        if x_session_id:
            session_obj = await get_session(redis, x_session_id)

        # 3) Load routing metrics and choose an upstream via the scheduler.
        base_weights: dict[str, float] = {
            up.provider_id: up.base_weight for up in candidates
        }
        metrics_by_provider: dict[str, RoutingMetrics] = (
            await _load_metrics_for_candidates(
                redis,
                logical_model.logical_id,
                candidates,
            )
        )
        dynamic_weights = await load_dynamic_weights(
            redis, logical_model.logical_id, candidates
        )
        strategy = SchedulingStrategy(
            name="balanced", description="Default chat routing strategy"
        )
        try:
            selected: CandidateScore
            selected, scored_candidates = choose_upstream(
                logical_model,
                candidates,
                metrics_by_provider,
                strategy,
                session=session_obj,
                dynamic_weights=dynamic_weights,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        ordered_candidates = _build_ordered_candidates(selected, scored_candidates)

        logger.info(
            "chat_completions: selected upstream provider=%s model=%s "
            "for logical_model=%s; candidates=%s",
            selected.upstream.provider_id,
            selected.upstream.model_id,
            logical_model.logical_id,
            [
                (
                    c.upstream.provider_id,
                    c.upstream.model_id,
                    round(c.score, 3),
                )
                for c in scored_candidates
            ],
        )

        async def _bind_session_for_upstream(
            provider_id: str,
            model_id: str,
        ) -> None:
            """
            Bind the conversation to the chosen upstream when stickiness
            is enabled. For non-streaming calls this is invoked after we
            have a final response; for streaming we call it on the first
            successfully yielded chunk.
            """
            if x_session_id and strategy.enable_stickiness:
                await bind_session(
                    redis,
                    conversation_id=x_session_id,
                    logical_model=logical_model.logical_id,
                    provider_id=provider_id,
                    model_id=model_id,
                )

        def _base_weight_for(provider_id: str) -> float:
            return base_weights.get(provider_id, 1.0)

        def _mark_provider_success(provider_id: str) -> None:
            record_provider_success(
                redis,
                logical_model.logical_id,
                provider_id,
                _base_weight_for(provider_id),
            )

        def _mark_provider_failure(provider_id: str, *, retryable: bool) -> None:
            record_provider_failure(
                redis,
                logical_model.logical_id,
                provider_id,
                _base_weight_for(provider_id),
                retryable=retryable,
            )

        if not stream:
            # Non-streaming mode: try candidates in order, falling back
            # to the next provider when we see a retryable upstream error.
            last_status: int | None = None
            last_error_text: str | None = None

            for cand in ordered_candidates:
                base_endpoint = cand.upstream.endpoint
                url = base_endpoint
                provider_id = cand.upstream.provider_id
                model_id = cand.upstream.model_id
                upstream_style = getattr(cand.upstream, "api_style", "openai")
                key_selection: SelectedProviderKey | None = None
                provider_cfg = get_provider_config(provider_id)
                if provider_cfg is None:
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_text = f"Provider '{provider_id}' is not configured"
                    continue
                if getattr(provider_cfg, "transport", "http") == "sdk":
                    driver = get_sdk_driver(provider_cfg)
                    if driver is None:
                        last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                        last_error_text = (
                            f"Provider '{provider_id}' 不支持 transport=sdk"
                        )
                        continue
                    try:
                        key_selection = await acquire_provider_key(
                            provider_cfg, redis
                        )
                    except NoAvailableProviderKey as exc:
                        last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                        last_error_text = str(exc)
                        _mark_provider_failure(provider_id, retryable=False)
                        continue

                    try:
                        sdk_payload = await call_sdk_generate_with_metrics(
                            driver=driver,
                            api_key=key_selection.key,
                            model_id=model_id,
                            payload=payload,
                            base_url=normalize_base_url(provider_cfg.base_url),
                            db=db,
                            provider_id=provider_id,
                            logical_model=logical_model.logical_id,
                            user_id=current_key.user_id,
                            api_key_id=current_key.id,
                        )
                    except Exception as exc:
                        last_status = None
                        last_error_text = str(exc)
                        record_key_failure(
                            key_selection,
                            retryable=True,
                            status_code=None,
                            redis=redis,
                        )
                        _mark_provider_failure(provider_id, retryable=True)
                        continue

                    await _bind_session_for_upstream(provider_id, model_id)
                    await save_context(
                        redis, x_session_id, payload, json.dumps(sdk_payload)
                    )
                    record_key_success(key_selection, redis=redis)
                    _mark_provider_success(provider_id)
                    converted_payload = sdk_payload
                    if (
                        driver.name == "google"
                        and api_style == "openai"
                        and isinstance(sdk_payload, dict)
                        and sdk_payload.get("candidates") is not None
                    ):
                        converted_payload = _build_openai_completion_from_gemini(
                            sdk_payload, payload.get("model") or model_id
                        )
                    # 记录一次非流式 SDK 调用的实际 token 消耗。
                    try:
                        record_chat_completion_usage(
                            db,
                            user_id=current_key.user_id,
                            api_key_id=current_key.id,
                            model_name=logical_model.logical_id,
                            provider_id=provider_id,
                            payload=converted_payload
                            if isinstance(converted_payload, dict)
                            else None,
                            is_stream=False,
                        )
                    except Exception:  # pragma: no cover - 防御性日志
                        logger.exception(
                            "Failed to record credit usage for SDK chat completion "
                            "(user=%s logical_model=%s)",
                            current_key.user_id,
                            logical_model.logical_id,
                        )
                    return JSONResponse(
                        content=converted_payload,
                        status_code=status.HTTP_200_OK,
                    )
                try:
                    headers, key_selection = await _build_provider_headers(
                        provider_cfg, redis
                    )
                except NoAvailableProviderKey as exc:
                    logger.warning(
                        "Provider %s has no available API keys: %s",
                        provider_id,
                        exc,
                    )
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_text = str(exc)
                    _mark_provider_failure(provider_id, retryable=False)
                    continue
                fallback_path = fallback_path_override or "/v1/chat/completions"
                fallback_url = (
                    _apply_upstream_path_override(base_endpoint, fallback_path)
                    if fallback_path
                    else None
                )

                preferred_messages_path: str | None = None
                if api_style == "claude":
                    preferred_messages_path = messages_path_override
                    if preferred_messages_path is None:
                        preferred_messages_path = provider_cfg.messages_path
                    if preferred_messages_path:
                        url = _apply_upstream_path_override(
                            url, preferred_messages_path
                        )
                    else:
                        outcome = await _send_claude_fallback_non_stream(
                            client=client,
                            headers=headers,
                            provider_id=provider_id,
                            model_id=model_id,
                            logical_model_id=logical_model.logical_id,
                            payload=payload,
                            fallback_url=fallback_url or base_endpoint,
                            redis=redis,
                            x_session_id=x_session_id,
                            bind_session=_bind_session_for_upstream,
                            db=db,
                            user_id=current_key.user_id,
                            api_key_id=current_key.id,
                        )
                        if outcome.response is not None:
                            if key_selection:
                                record_key_success(key_selection, redis=redis)
                            _mark_provider_success(provider_id)
                            # 从 Fallback 响应中提取 usage 信息做扣费。
                            billing_payload = None
                            try:
                                body_bytes = outcome.response.body
                                if isinstance(body_bytes, (bytes, bytearray)):
                                    billing_payload = json.loads(
                                        body_bytes.decode("utf-8")
                                    )
                            except Exception:  # pragma: no cover - 防御性日志
                                billing_payload = None
                            try:
                                record_chat_completion_usage(
                                    db,
                                    user_id=current_key.user_id,
                                    api_key_id=current_key.id,
                                    model_name=logical_model.logical_id,
                                    provider_id=provider_id,
                                    payload=billing_payload
                                    if isinstance(billing_payload, dict)
                                    else None,
                                    is_stream=False,
                                )
                            except Exception:  # pragma: no cover - 防御性日志
                                logger.exception(
                                    "Failed to record credit usage for Claude fallback "
                                    "(user=%s logical_model=%s)",
                                    current_key.user_id,
                                    logical_model.logical_id,
                                )
                            return outcome.response
                        last_status = outcome.status_code
                        last_error_text = outcome.error_text
                        if outcome.retryable:
                            if key_selection:
                                record_key_failure(
                                    key_selection,
                                    retryable=True,
                                    status_code=outcome.status_code,
                                    redis=redis,
                                )
                            _mark_provider_failure(provider_id, retryable=True)
                            continue
                        detail = outcome.error_text or (
                            f"Upstream error {outcome.status_code or '?'}"
                        )
                        logger.warning(
                            "Claude fallback non-streaming failed for provider=%s model=%s: %s",
                            provider_id,
                            model_id,
                            detail,
                        )
                        await save_context(redis, x_session_id, payload, detail)
                        if key_selection:
                            record_key_failure(
                                key_selection,
                                retryable=False,
                                status_code=outcome.status_code,
                                redis=redis,
                            )
                        _mark_provider_failure(provider_id, retryable=False)
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=detail,
                        )

                if api_style == "responses" and upstream_style == "openai":
                    outcome = await _send_responses_fallback_non_stream(
                        client=client,
                        headers=headers,
                        provider_id=provider_id,
                        model_id=model_id,
                        logical_model_id=logical_model.logical_id,
                        payload=payload,
                        target_url=base_endpoint,
                        redis=redis,
                        x_session_id=x_session_id,
                        bind_session=_bind_session_for_upstream,
                        db=db,
                        user_id=current_key.user_id,
                        api_key_id=current_key.id,
                    )
                    if outcome.response is not None:
                        if key_selection:
                            record_key_success(key_selection, redis=redis)
                        _mark_provider_success(provider_id)
                        billing_payload = None
                        try:
                            body_bytes = outcome.response.body
                            if isinstance(body_bytes, (bytes, bytearray)):
                                billing_payload = json.loads(
                                    body_bytes.decode("utf-8")
                                )
                        except Exception:  # pragma: no cover - 防御性日志
                            billing_payload = None
                        try:
                            record_chat_completion_usage(
                                db,
                                user_id=current_key.user_id,
                                api_key_id=current_key.id,
                                model_name=logical_model.logical_id,
                                provider_id=provider_id,
                                payload=billing_payload
                                if isinstance(billing_payload, dict)
                                else None,
                                is_stream=False,
                            )
                        except Exception:  # pragma: no cover - 防御性日志
                            logger.exception(
                                "Failed to record credit usage for Responses fallback "
                                "(user=%s logical_model=%s)",
                                current_key.user_id,
                                logical_model.logical_id,
                            )
                        return outcome.response
                    last_status = outcome.status_code
                    last_error_text = outcome.error_text
                    if outcome.retryable:
                        if key_selection:
                            record_key_failure(
                                key_selection,
                                retryable=True,
                                status_code=outcome.status_code,
                                redis=redis,
                            )
                        _mark_provider_failure(provider_id, retryable=True)
                        continue
                    detail = outcome.error_text or (
                        f"Upstream error {outcome.status_code or '?'}"
                    )
                    logger.warning(
                        "Responses fallback failed for provider=%s model=%s: %s",
                        provider_id,
                        model_id,
                        detail,
                    )
                    await save_context(redis, x_session_id, payload, detail)
                    if key_selection:
                        record_key_failure(
                            key_selection,
                            retryable=False,
                            status_code=outcome.status_code,
                            redis=redis,
                        )
                    _mark_provider_failure(provider_id, retryable=False)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=detail,
                    )

                logger.info(
                    "chat_completions: sending non-streaming request to "
                    "provider=%s model=%s url=%s",
                    provider_id,
                    model_id,
                    url,
                )

                # Use a provider-specific model id when forwarding
                # upstream so that grouped ids like "provider-2/xxx"
                # are translated correctly for each vendor.
                upstream_payload = dict(payload)
                upstream_payload["model"] = model_id

                try:
                    r = await call_upstream_http_with_metrics(
                        client=client,
                        url=url,
                        headers=headers,
                        json_body=upstream_payload,
                        db=db,
                        provider_id=provider_id,
                        logical_model=logical_model.logical_id,
                        user_id=current_key.user_id,
                        api_key_id=current_key.id,
                    )
                except httpx.HTTPError as exc:
                    if key_selection:
                        record_key_failure(
                            key_selection,
                            retryable=True,
                            status_code=None,
                            redis=redis,
                        )
                    _mark_provider_failure(provider_id, retryable=True)
                    logger.warning(
                        "Upstream non-streaming request error for %s "
                        "(provider=%s, model=%s): %s; trying next candidate",
                        url,
                        provider_id,
                        model_id,
                        exc,
                    )
                    last_status = None
                    last_error_text = str(exc)
                    continue

                text = r.text
                status_code = r.status_code

                logger.info(
                    "chat_completions: upstream non-streaming response "
                    "status=%s provider=%s model=%s body_length=%d",
                    status_code,
                    provider_id,
                    model_id,
                    len(text or ""),
                )

                if _should_attempt_claude_messages_fallback(
                    api_style=api_style,
                    upstream_path_override=preferred_messages_path,
                    status_code=status_code,
                    response_text=text,
                ):
                    outcome = await _send_claude_fallback_non_stream(
                        client=client,
                        headers=headers,
                        provider_id=provider_id,
                        model_id=model_id,
                        logical_model_id=logical_model.logical_id,
                        payload=payload,
                        fallback_url=fallback_url or base_endpoint,
                        redis=redis,
                        x_session_id=x_session_id,
                        bind_session=_bind_session_for_upstream,
                        db=db,
                        user_id=current_key.user_id,
                        api_key_id=current_key.id,
                    )
                    if outcome.response is not None:
                        if key_selection:
                            record_key_success(key_selection, redis=redis)
                        _mark_provider_success(provider_id)
                        return outcome.response
                    last_status = outcome.status_code
                    last_error_text = outcome.error_text
                    if outcome.retryable:
                        if key_selection:
                            record_key_failure(
                                key_selection,
                                retryable=True,
                                status_code=outcome.status_code,
                                redis=redis,
                            )
                        _mark_provider_failure(provider_id, retryable=True)
                        continue
                    detail = outcome.error_text or (
                        f"Upstream error {outcome.status_code or '?'}"
                    )
                    logger.warning(
                        "Claude fallback non-streaming failed for provider=%s model=%s: %s",
                        provider_id,
                        model_id,
                        detail,
                    )
                    await save_context(redis, x_session_id, payload, detail)
                    if key_selection:
                        record_key_failure(
                            key_selection,
                            retryable=False,
                            status_code=outcome.status_code,
                        )
                    _mark_provider_failure(provider_id, retryable=False)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=detail,
                    )

                if status_code >= 400 and _is_retryable_upstream_status(
                    provider_id, status_code
                ):
                    if key_selection:
                        record_key_failure(
                            key_selection,
                            retryable=True,
                            status_code=status_code,
                            redis=redis,
                        )
                    logger.warning(
                        "Upstream non-streaming retryable error %s for %s "
                        "(provider=%s, model=%s); payload=%r; response=%s",
                        status_code,
                        url,
                        provider_id,
                        model_id,
                        payload,
                        text,
                    )
                    last_status = status_code
                    last_error_text = text
                    _mark_provider_failure(provider_id, retryable=True)
                    # Try next candidate.
                    continue

                # At this point we either have a successful response
                # (<400) or a non-retryable 4xx.
                await _bind_session_for_upstream(provider_id, model_id)
                await save_context(redis, x_session_id, payload, text)

                if status_code >= 400:
                    if key_selection:
                        record_key_failure(
                            key_selection,
                            retryable=False,
                            status_code=status_code,
                            redis=redis,
                        )
                    _mark_provider_failure(provider_id, retryable=False)
                    logger.warning(
                        "Upstream non-streaming non-retryable error %s for %s "
                        "(provider=%s, model=%s); payload=%r; response=%s",
                        status_code,
                        url,
                        provider_id,
                        model_id,
                        payload,
                        text,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Upstream error {status_code}: {text}",
                    )

                if key_selection:
                    record_key_success(key_selection, redis=redis)
                _mark_provider_success(provider_id)
                converted_payload: Any
                try:
                    converted_payload = r.json()
                except ValueError:
                    converted_payload = None

                if (
                    api_style == "openai"
                    and _GEMINI_MODEL_REGEX.search(model_id or "")
                    and isinstance(converted_payload, dict)
                    and converted_payload.get("candidates") is not None
                ):
                    converted_payload = _build_openai_completion_from_gemini(
                        converted_payload, payload.get("model") or model_id
                    )

                if converted_payload is not None:
                    # 记录一次非流式 HTTP 调用的 token 消耗。
                    try:
                        record_chat_completion_usage(
                            db,
                            user_id=current_key.user_id,
                            api_key_id=current_key.id,
                            model_name=logical_model.logical_id,
                            provider_id=provider_id,
                            payload=converted_payload
                            if isinstance(converted_payload, dict)
                            else None,
                            is_stream=False,
                        )
                    except Exception:  # pragma: no cover - 防御性日志
                        logger.exception(
                            "Failed to record credit usage for chat completion "
                            "(user=%s logical_model=%s)",
                            current_key.user_id,
                            logical_model.logical_id,
                        )
                    return JSONResponse(
                        content=converted_payload,
                        status_code=status_code,
                    )

                # 响应体无法解析为结构化 JSON 时，只记录一次 0-token 的占位流水。
                try:
                    record_chat_completion_usage(
                        db,
                        user_id=current_key.user_id,
                        api_key_id=current_key.id,
                        model_name=logical_model.logical_id,
                        provider_id=provider_id,
                        payload=None,
                        is_stream=False,
                    )
                except Exception:  # pragma: no cover - 防御性日志
                    logger.exception(
                        "Failed to record credit usage for raw chat completion "
                        "(user=%s logical_model=%s)",
                        current_key.user_id,
                        logical_model.logical_id,
                    )
                return JSONResponse(
                    content={"raw": text},
                    status_code=status_code,
                )

            # All candidates failed with retryable errors.
            message = (
                f"All upstream providers failed for logical model "
                f"'{logical_model.logical_id}'"
            )
            details: list[str] = []
            if last_status is not None:
                details.append(f"last_status={last_status}")
            if last_error_text:
                details.append(f"last_error={last_error_text}")
            detail_text = message
            if details:
                detail_text = f"{message}; " + ", ".join(details)

            logger.error(detail_text)
            await save_context(redis, x_session_id, payload, detail_text)

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=detail_text,
            )

        # Streaming mode via candidate providers.
        async def routed_iterator() -> AsyncIterator[bytes]:
            last_status: int | None = None
            last_error_text: str | None = None

            for idx, cand in enumerate(ordered_candidates):
                base_endpoint = cand.upstream.endpoint
                url = base_endpoint
                provider_id = cand.upstream.provider_id
                model_id = cand.upstream.model_id
                upstream_style = getattr(cand.upstream, "api_style", "openai")
                key_selection: SelectedProviderKey | None = None
                provider_cfg = get_provider_config(provider_id)
                if provider_cfg is None:
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_text = f"Provider '{provider_id}' is not configured"
                    continue
                if getattr(provider_cfg, "transport", "http") == "sdk":
                    driver = get_sdk_driver(provider_cfg)
                    if driver is None:
                        last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                        last_error_text = (
                            f"Provider '{provider_id}' 不支持 transport=sdk"
                        )
                        continue
                    try:
                        key_selection = await acquire_provider_key(
                            provider_cfg, redis
                        )
                    except NoAvailableProviderKey as exc:
                        last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                        last_error_text = str(exc)
                        _mark_provider_failure(provider_id, retryable=False)
                        continue

                    adapter = None
                    if driver.name == "google":
                        adapter = GeminiToOpenAIStreamAdapter(
                            payload.get("model") or model_id
                        )

                    first_chunk_seen = False
                    try:
                        async for chunk_dict in stream_sdk_with_metrics(
                            driver=driver,
                            api_key=key_selection.key,
                            model_id=model_id,
                            payload=payload,
                            base_url=normalize_base_url(provider_cfg.base_url),
                            redis=redis,
                            session_id=x_session_id,
                            db=db,
                            provider_id=provider_id,
                            logical_model=logical_model.logical_id,
                            user_id=current_key.user_id,
                            api_key_id=current_key.id,
                        ):
                            if not first_chunk_seen:
                                first_chunk_seen = True
                                await _bind_session_for_upstream(
                                    provider_id, model_id
                                )
                                logger.info(
                                    "chat_completions: received first streaming "
                                    "chunk from provider=%s model=%s (sdk driver)",
                                    provider_id,
                                    model_id,
                                )
                            if adapter:
                                converted = adapter.process_chunk(chunk_dict)
                                for item in converted:
                                    yield item
                            else:
                                yield json.dumps(chunk_dict).encode("utf-8") + b"\n"

                        logger.info(
                            "chat_completions: streaming finished successfully "
                            "for provider=%s model=%s (sdk driver)",
                            provider_id,
                            model_id,
                        )
                        if adapter:
                            for tail in adapter.finalize():
                                yield tail
                        if key_selection:
                            record_key_success(key_selection, redis=redis)
                        _mark_provider_success(provider_id)
                        return
                    except Exception as exc:
                        last_status = None
                        last_error_text = str(exc)
                        record_key_failure(
                            key_selection,
                            retryable=True,
                            status_code=None,
                            redis=redis,
                        )
                        _mark_provider_failure(provider_id, retryable=True)
                        continue
                try:
                    headers, key_selection = await _build_provider_headers(
                        provider_cfg, redis
                    )
                except NoAvailableProviderKey as exc:
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_text = str(exc)
                    _mark_provider_failure(provider_id, retryable=False)
                    continue
                is_last = idx == len(ordered_candidates) - 1
                fallback_path = fallback_path_override or "/v1/chat/completions"
                fallback_url = (
                    _apply_upstream_path_override(base_endpoint, fallback_path)
                    if fallback_path
                    else None
                )
                preferred_messages_path: str | None = None
                if api_style == "claude":
                    preferred_messages_path = messages_path_override
                    if preferred_messages_path is None:
                        preferred_messages_path = provider_cfg.messages_path
                    if preferred_messages_path:
                        url = _apply_upstream_path_override(
                            url, preferred_messages_path
                        )
                    else:
                        async for chunk in _claude_streaming_fallback_iterator(
                            client=client,
                            headers=headers,
                            provider_id=provider_id,
                            model_id=model_id,
                            logical_model_id=logical_model.logical_id,
                            fallback_url=fallback_url or base_endpoint,
                            payload=payload,
                            redis=redis,
                            session_id=x_session_id,
                            bind_session_cb=_bind_session_for_upstream,
                            db=db,
                            user_id=current_key.user_id,
                            api_key_id=current_key.id,
                        ):
                            yield chunk
                        if key_selection:
                            record_key_success(key_selection, redis=redis)
                        _mark_provider_success(provider_id)
                        return
                stream_adapter: GeminiToOpenAIStreamAdapter | None = None
                if api_style == "openai" and _GEMINI_MODEL_REGEX.search(
                    model_id or ""
                ):
                    stream_adapter = GeminiToOpenAIStreamAdapter(
                        payload.get("model") or model_id
                    )

                logger.info(
                    "chat_completions: starting streaming request to "
                    "provider=%s model=%s url=%s (candidate %d/%d)",
                    provider_id,
                    model_id,
                    url,
                    idx + 1,
                    len(ordered_candidates),
                )

                try:
                    first_chunk = True
                    upstream_payload = dict(payload)
                    upstream_payload["model"] = model_id

                    async for chunk in stream_upstream_with_metrics(
                        client=client,
                        method="POST",
                        url=url,
                        headers=headers,
                        json_body=upstream_payload,
                        redis=redis,
                        session_id=x_session_id,
                        db=db,
                        provider_id=provider_id,
                        logical_model=logical_model.logical_id,
                        user_id=current_key.user_id,
                        api_key_id=current_key.id,
                    ):
                        if first_chunk:
                            first_chunk = False
                            await _bind_session_for_upstream(
                                provider_id, model_id
                            )
                            logger.info(
                                "chat_completions: received first streaming "
                                "chunk from provider=%s model=%s",
                                provider_id,
                                model_id,
                            )
                        if stream_adapter:
                            converted = stream_adapter.process_chunk(chunk)
                            for item in converted:
                                yield item
                        else:
                            yield chunk

                    # Stream finished successfully, stop iterating.
                    logger.info(
                        "chat_completions: streaming finished successfully "
                        "for provider=%s model=%s",
                        provider_id,
                        model_id,
                    )
                    if stream_adapter:
                        for tail in stream_adapter.finalize():
                            yield tail
                    if key_selection:
                        record_key_success(key_selection, redis=redis)
                    _mark_provider_success(provider_id)
                    return
                except UpstreamStreamError as err:
                    last_status = err.status_code
                    last_error_text = err.text
                    retryable = _is_retryable_upstream_status(
                        provider_id, err.status_code
                    )

                    if _should_attempt_claude_messages_fallback(
                        api_style=api_style,
                        upstream_path_override=preferred_messages_path,
                        status_code=err.status_code,
                        response_text=err.text,
                    ):
                        try:
                            async for chunk in _claude_streaming_fallback_iterator(
                                client=client,
                                headers=headers,
                                provider_id=provider_id,
                                model_id=model_id,
                                logical_model_id=logical_model.logical_id,
                                fallback_url=fallback_url or base_endpoint,
                                payload=payload,
                                redis=redis,
                                session_id=x_session_id,
                                bind_session_cb=_bind_session_for_upstream,
                                db=db,
                                user_id=current_key.user_id,
                                api_key_id=current_key.id,
                            ):
                                yield chunk
                            if key_selection:
                                record_key_success(key_selection, redis=redis)
                            _mark_provider_success(provider_id)
                            return
                        except ClaudeMessagesFallbackStreamError as fallback_err:
                            last_status = fallback_err.status_code
                            last_error_text = fallback_err.text
                            retryable = fallback_err.retryable

                    logger.warning(
                        "Upstream streaming error for %s "
                        "(provider=%s, model=%s, status=%s); retryable=%s",
                        url,
                        provider_id,
                        model_id,
                        err.status_code,
                        retryable,
                    )

                    if retryable and not is_last:
                        if key_selection:
                            record_key_failure(
                                key_selection,
                                retryable=True,
                                status_code=err.status_code,
                                redis=redis,
                            )
                        _mark_provider_failure(provider_id, retryable=True)
                        # Try next candidate without sending anything
                        # downstream yet.
                        continue

                    # Either not retryable or no more candidates: emit a
                    # final SSE-style error frame and stop.
                    if key_selection:
                        record_key_failure(
                            key_selection,
                            retryable=retryable,
                            status_code=err.status_code,
                            redis=redis,
                        )
                    _mark_provider_failure(provider_id, retryable=retryable)
                    try:
                        payload_json = json.loads(err.text)
                    except json.JSONDecodeError:
                        payload_json = {
                            "error": {
                                "type": "upstream_error",
                                "status": err.status_code,
                                "message": err.text,
                            }
                        }

                    error_chunk = (
                        f"data: {json.dumps(payload_json, ensure_ascii=False)}\n\n"
                    ).encode()

                    # Save error into context for debugging.
                    await save_context(
                        redis,
                        x_session_id,
                        payload,
                        error_chunk.decode("utf-8", errors="ignore"),
                    )

                    yield error_chunk
                    return

            # Safety net: if the loop exits unexpectedly, emit a generic error.
            generic_payload = {
                "error": {
                    "type": "upstream_error",
                    "status": last_status,
                    "message": last_error_text
                    or "All upstream providers failed during streaming",
                }
            }
            error_chunk = (
                f"data: {json.dumps(generic_payload, ensure_ascii=False)}\n\n"
            ).encode()

            await save_context(
                redis,
                x_session_id,
                payload,
                error_chunk.decode("utf-8", errors="ignore"),
            )

            yield error_chunk

        # 在开始返回流式响应之前，基于请求参数预估一次积分扣费。
        # 这里使用候选列表中的首选 Provider 作为计费参考。
        try:
            primary_provider_id: str | None = None
            if ordered_candidates:
                primary_provider_id = ordered_candidates[0].upstream.provider_id

            record_streaming_request(
                db,
                user_id=current_key.user_id,
                api_key_id=current_key.id,
                model_name=logical_model.logical_id,
                provider_id=primary_provider_id,
                payload=payload,
            )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to record streaming credit usage for user %s model=%s",
                current_key.user_id,
                logical_model.logical_id,
            )

        return StreamingResponse(routed_iterator(), media_type="text/event-stream")


@router.post("/v1/responses")
async def responses_endpoint(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    raw_body: dict[str, Any] = Body(...),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    OpenAI Responses API 兼容端点，默认以 Responses 形态透传到上游。
    """
    passthrough_payload = dict(raw_body)
    passthrough_payload["_apiproxy_api_style"] = "responses"
    passthrough_payload["_apiproxy_skip_normalize"] = True
    passthrough = True
    forward_body = (
        passthrough_payload if passthrough else _adapt_responses_payload(raw_body)
    )

    base_response = await chat_completions(
        request=request,
        client=client,
        redis=redis,
        x_session_id=x_session_id,
        raw_body=forward_body,
        current_key=current_key,
    )
    if isinstance(base_response, StreamingResponse):
        if passthrough:
            return base_response
        return _wrap_chat_stream_response(base_response)

    if isinstance(base_response, JSONResponse):
        if passthrough:
            return base_response
        try:
            payload_bytes = base_response.body
            chat_payload = json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            return base_response

        responses_payload = _chat_to_responses_payload(chat_payload)
        headers = dict(base_response.headers)
        headers.pop("content-length", None)
        return JSONResponse(
            content=responses_payload,
            status_code=base_response.status_code,
            headers=headers,
        )
    return base_response


@router.post("/v1/messages")
async def claude_messages_endpoint(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    raw_body: dict[str, Any] = Body(...),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    Claude/Anthropic Messages API 兼容端点，向上游的 /v1/message 转发。
    """
    forward_body = dict(raw_body)
    forward_body["_apiproxy_api_style"] = "claude"
    forward_body["_apiproxy_skip_normalize"] = True
    forward_body["_apiproxy_messages_path"] = "/v1/message"
    forward_body["_apiproxy_fallback_path"] = "/v1/chat/completions"

    return await chat_completions(
        request=request,
        client=client,
        redis=redis,
        x_session_id=x_session_id,
        raw_body=forward_body,
        current_key=current_key,
    )


__all__ = ["router"]
