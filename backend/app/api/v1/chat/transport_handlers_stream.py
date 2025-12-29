"""
流式传输层处理（v2）

输出约定：返回的 bytes 直接作为网关响应 body（SSE/事件流），保持与请求 api_style 一致。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from sqlalchemy.orm import Session as DbSession

from app.api.v1.chat.header_builder import build_upstream_headers
from app.api.v1.chat.protocol_adapter import adapt_request_payload
from app.api.v1.chat.protocol_stream_adapter import adapt_stream
from app.api.v1.chat.provider_endpoint_resolver import resolve_http_upstream_target
from app.api.v1.chat.sdk_stream_encoder import (
    GeminiDictToOpenAISSEAdapter,
    encode_claude_sdk_event_dict,
    encode_openai_done,
    encode_openai_sdk_chunk_dict,
)
from app.api.v1.chat.upstream_error_classifier import classify_capability_mismatch
from app.auth import AuthenticatedAPIKey
from app.provider import config as provider_config
from app.provider.key_pool import (
    NoAvailableProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)
from app.provider.sdk_selector import get_sdk_driver, normalize_base_url
from app.services.chat_routing_service import (
    _GEMINI_MODEL_REGEX,
    _is_retryable_upstream_status,
)
from app.services.claude_cli_transformer import build_claude_cli_headers, transform_to_claude_cli_format
from app.services.metrics_service import stream_sdk_with_metrics, stream_upstream_with_metrics
from app.upstream import UpstreamStreamError


async def execute_http_stream(
    *,
    client: httpx.AsyncClient,
    redis: Redis,
    db: DbSession,
    provider_id: str,
    model_id: str,
    url: str,
    payload: dict[str, Any],
    logical_model_id: str,
    api_style: str,
    upstream_api_style: str = "openai",
    api_key: AuthenticatedAPIKey,
    messages_path_override: str | None = None,
    fallback_path_override: str | None = None,
) -> AsyncIterator[bytes]:
    provider_cfg = provider_config.get_provider_config(provider_id)
    if provider_cfg is None:
        raise Exception(f"Provider '{provider_id}' is not configured")

    try:
        key_selection = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        raise Exception(str(exc))

    async def _noop_bind_session(_provider_id: str, _model_id: str) -> None:
        return

    target = resolve_http_upstream_target(
        provider_cfg,
        requested_api_style=api_style,
        default_url=url,
        default_upstream_style=upstream_api_style,
        messages_path_override=messages_path_override,
        fallback_path_override=fallback_path_override,
    )
    call_style = target.api_style
    call_url = target.url

    headers = build_upstream_headers(key_selection.key, provider_cfg, call_style=call_style, is_stream=True)

    try:
        upstream_payload = adapt_request_payload(
            payload,
            from_style=api_style,
            to_style=call_style,
            upstream_model_id=model_id,
        )
    except Exception as exc:
        record_key_failure(key_selection, retryable=False, status_code=400, redis=redis)
        raise Exception(f"Failed to adapt request payload: {exc}")

    upstream_payload["stream"] = True

    async def _upstream_iter() -> AsyncIterator[bytes]:
        sse_style = call_style if call_style in ("openai", "claude") else "openai"
        async for chunk in stream_upstream_with_metrics(
            client=client,
            method="POST",
            url=call_url,
            headers=headers,
            json_body=upstream_payload,
            redis=redis,
            sse_style=sse_style,
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
        ):
            yield chunk

    try:
        iterator: AsyncIterator[bytes] = _upstream_iter()
        if call_style != api_style:
            iterator = adapt_stream(
                iterator,
                from_style=call_style,
                to_style=api_style,
                request_model=str(payload.get("model") or model_id),
            )
        async for chunk in iterator:
            yield chunk
        record_key_success(key_selection, redis=redis)
    except UpstreamStreamError as err:
        mismatch = classify_capability_mismatch(err.status_code, getattr(err, "text", None))
        retryable = True if mismatch else _is_retryable_upstream_status(provider_id, err.status_code)
        if mismatch:
            err.retryable = True
            err.penalize = False
            raise
        record_key_failure(
            key_selection,
            retryable=retryable,
            status_code=err.status_code,
            redis=redis,
        )
        raise
    except Exception:
        record_key_failure(key_selection, retryable=True, status_code=None, redis=redis)
        raise


async def execute_sdk_stream(
    *,
    redis: Redis,
    db: DbSession,
    provider_id: str,
    model_id: str,
    payload: dict[str, Any],
    logical_model_id: str,
    api_style: str,
    api_key: AuthenticatedAPIKey,
) -> AsyncIterator[bytes]:
    provider_cfg = provider_config.get_provider_config(provider_id)
    if provider_cfg is None:
        raise Exception(f"Provider '{provider_id}' is not configured")

    driver = get_sdk_driver(provider_cfg)
    if driver is None:
        raise Exception(f"Provider '{provider_id}' 不支持 transport=sdk")

    try:
        key_selection = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        raise Exception(str(exc))

    driver_name = str(getattr(driver, "name", "") or "").lower()

    upstream_style: str = "openai"
    if driver_name in ("anthropic", "claude"):
        upstream_style = "claude"

    upstream_payload = adapt_request_payload(
        payload,
        from_style=api_style,
        to_style=upstream_style,
        upstream_model_id=model_id,
    )
    upstream_payload["stream"] = True

    async def _encoded_upstream_iter() -> AsyncIterator[bytes]:
        if upstream_style == "claude":
            async for event_dict in stream_sdk_with_metrics(
                driver=driver,
                api_key=key_selection.key,
                model_id=model_id,
                payload=upstream_payload,
                base_url=normalize_base_url(provider_cfg.base_url),
                db=db,
                provider_id=provider_id,
                logical_model=logical_model_id,
                user_id=api_key.user_id,
                api_key_id=api_key.id,
            ):
                if isinstance(event_dict, dict):
                    yield encode_claude_sdk_event_dict(event_dict)
            return

        # upstream_style == openai
        gemini_adapter: GeminiDictToOpenAISSEAdapter | None = None
        if driver_name in ("google", "vertexai") and _GEMINI_MODEL_REGEX.search(
            str(payload.get("model") or model_id or "")
        ):
            gemini_adapter = GeminiDictToOpenAISSEAdapter(payload.get("model") or model_id)

        async for chunk_dict in stream_sdk_with_metrics(
            driver=driver,
            api_key=key_selection.key,
            model_id=model_id,
            payload=upstream_payload,
            base_url=normalize_base_url(provider_cfg.base_url),
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
        ):
            if not isinstance(chunk_dict, dict):
                continue
            if gemini_adapter is not None:
                for out in gemini_adapter.process_chunk(chunk_dict):
                    yield out
            else:
                yield encode_openai_sdk_chunk_dict(chunk_dict)

        if gemini_adapter is not None:
            for tail in gemini_adapter.finalize():
                yield tail
        else:
            yield encode_openai_done()

    try:
        iterator: AsyncIterator[bytes] = _encoded_upstream_iter()
        if upstream_style != api_style:
            iterator = adapt_stream(
                iterator,
                from_style=upstream_style,
                to_style=api_style,
                request_model=str(payload.get("model") or model_id),
            )
        async for chunk in iterator:
            yield chunk
        record_key_success(key_selection, redis=redis)
    except Exception:
        record_key_failure(key_selection, retryable=True, status_code=None, redis=redis)
        raise


async def execute_claude_cli_stream(
    *,
    client: httpx.AsyncClient,
    redis: Redis,
    db: DbSession,
    provider_id: str,
    model_id: str,
    payload: dict[str, Any],
    logical_model_id: str,
    api_style: str,
    api_key: AuthenticatedAPIKey,
) -> AsyncIterator[bytes]:
    provider_cfg = provider_config.get_provider_config(provider_id)
    if provider_cfg is None:
        raise Exception(f"Provider '{provider_id}' is not configured")

    try:
        key_selection = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        raise Exception(str(exc))

    try:
        claude_cli_headers = build_claude_cli_headers(key_selection.key)
        openai_payload = adapt_request_payload(
            payload,
            from_style=api_style,
            to_style="openai",
            upstream_model_id=model_id,
        )
        claude_payload = transform_to_claude_cli_format(
            openai_payload,
            api_key=key_selection.key,
            session_id=None,
        )
    except Exception as exc:
        raise Exception(f"Failed to build Claude CLI request: {exc}")

    claude_payload["stream"] = True
    claude_url = f"{str(provider_cfg.base_url).rstrip('/')}/v1/messages?beta=true"

    async def _claude_iter() -> AsyncIterator[bytes]:
        async for chunk in stream_upstream_with_metrics(
            client=client,
            method="POST",
            url=claude_url,
            headers=claude_cli_headers,
            json_body=claude_payload,
            redis=redis,
            sse_style="claude",
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
        ):
            yield chunk

    try:
        iterator: AsyncIterator[bytes] = _claude_iter()
        if api_style != "claude":
            iterator = adapt_stream(
                iterator,
                from_style="claude",
                to_style=api_style,
                request_model=str(payload.get("model") or model_id),
            )
        async for chunk in iterator:
            yield chunk
        record_key_success(key_selection, redis=redis)
    except UpstreamStreamError as err:
        mismatch = classify_capability_mismatch(err.status_code, getattr(err, "text", None))
        retryable = True if mismatch else _is_retryable_upstream_status(provider_id, err.status_code)
        if mismatch:
            err.retryable = True
            err.penalize = False
            raise
        record_key_failure(
            key_selection,
            retryable=retryable,
            status_code=err.status_code,
            redis=redis,
        )
        raise
    except Exception:
        record_key_failure(key_selection, retryable=True, status_code=None, redis=redis)
        raise


__all__ = [
    "execute_claude_cli_stream",
    "execute_http_stream",
    "execute_sdk_stream",
]
