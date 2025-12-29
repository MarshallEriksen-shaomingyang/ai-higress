"""
非流式传输层处理（v2）

负责按 provider.transport 执行一次上游调用，并返回：
- success + JSONResponse（保持与请求 api_style 一致的响应形态）
- 或失败信息（status_code/error_text/retryable）供候选重试逻辑使用
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi.responses import JSONResponse

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from sqlalchemy.orm import Session as DbSession

from app.api.v1.chat.header_builder import build_upstream_headers
from app.api.v1.chat.protocol_adapter import (
    adapt_request_payload,
    adapt_response_payload,
    stringify_payload,
)
from app.api.v1.chat.provider_endpoint_resolver import resolve_http_upstream_target
from app.api.v1.chat.upstream_error_classifier import classify_capability_mismatch
from app.auth import AuthenticatedAPIKey
from app.provider import config as provider_config
from app.provider.config import ProviderConfig
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
from app.services.claude_cli_transformer import (
    build_claude_cli_headers,
    transform_to_claude_cli_format,
)
from app.services.metrics_service import call_sdk_generate_with_metrics, call_upstream_http_with_metrics


class TransportResult:
    def __init__(
        self,
        *,
        success: bool,
        response: JSONResponse | None = None,
        status_code: int | None = None,
        error_text: str | None = None,
        retryable: bool = False,
        penalize: bool = True,
        error_category: str | None = None,
    ) -> None:
        self.success = success
        self.response = response
        self.status_code = status_code
        self.error_text = error_text
        self.retryable = retryable
        self.penalize = penalize
        self.error_category = error_category


def _build_headers(api_key: str, provider_cfg: ProviderConfig) -> dict[str, str]:
    """
    向后兼容的 header 构建函数（仅用于历史测试与少量调用方）。

    生产路径请使用 `_build_headers_for_style` 以支持 Claude 的 `x-api-key`
    及浏览器伪装相关 header。
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    if provider_cfg.custom_headers:
        headers.update(provider_cfg.custom_headers)
    return headers


async def execute_http_transport(
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
) -> TransportResult:
    provider_cfg = provider_config.get_provider_config(provider_id)
    if provider_cfg is None:
        return TransportResult(
            success=False,
            status_code=503,
            error_text=f"Provider '{provider_id}' is not configured",
            retryable=False,
        )

    try:
        key_selection = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        return TransportResult(
            success=False,
            status_code=503,
            error_text=str(exc),
            retryable=False,
        )

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

    headers = build_upstream_headers(
        key_selection.key, provider_cfg, call_style=call_style, is_stream=False
    )

    try:
        upstream_payload = adapt_request_payload(
            payload,
            from_style=api_style,
            to_style=call_style,
            upstream_model_id=model_id,
        )
    except Exception as exc:
        record_key_failure(key_selection, retryable=False, status_code=400, redis=redis)
        return TransportResult(
            success=False,
            status_code=400,
            error_text=f"Failed to adapt request payload: {exc}",
            retryable=False,
        )

    try:
        r = await call_upstream_http_with_metrics(
            client=client,
            url=call_url,
            headers=headers,
            json_body=upstream_payload,
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
        )
    except httpx.HTTPError as exc:
        record_key_failure(key_selection, retryable=True, status_code=None, redis=redis)
        return TransportResult(success=False, error_text=str(exc), retryable=True)

    status_code = r.status_code
    text = r.text
    if status_code >= 400:
        mismatch = classify_capability_mismatch(status_code, text)
        if mismatch:
            # 该 provider/模型不支持某能力：对路由来说是“换 provider 重试”，但不应惩罚该 provider/key。
            return TransportResult(
                success=False,
                status_code=status_code,
                error_text=text,
                retryable=True,
                penalize=False,
                error_category=f"capability_mismatch:{mismatch}",
            )

        retryable = _is_retryable_upstream_status(provider_id, status_code)
        record_key_failure(
            key_selection,
            retryable=retryable,
            status_code=status_code,
            redis=redis,
        )
        return TransportResult(
            success=False,
            status_code=status_code,
            error_text=text,
            retryable=retryable,
        )

    record_key_success(key_selection, redis=redis)
    try:
        content = r.json()
    except ValueError:
        content = {"raw": text}

    try:
        adapted = adapt_response_payload(
            content,
            from_style=call_style,
            to_style=api_style,
            request_model=str(payload.get("model") or model_id),
        )
    except Exception:
        adapted = content

    return TransportResult(
        success=True,
        response=JSONResponse(content=adapted, status_code=status_code),
    )


async def execute_sdk_transport(
    *,
    redis: Redis,
    db: DbSession,
    provider_id: str,
    model_id: str,
    payload: dict[str, Any],
    logical_model_id: str,
    api_style: str,
    api_key: AuthenticatedAPIKey,
) -> TransportResult:
    provider_cfg = provider_config.get_provider_config(provider_id)
    if provider_cfg is None:
        return TransportResult(
            success=False,
            status_code=503,
            error_text=f"Provider '{provider_id}' is not configured",
            retryable=False,
        )

    driver = get_sdk_driver(provider_cfg)
    if driver is None:
        return TransportResult(
            success=False,
            status_code=503,
            error_text=f"Provider '{provider_id}' 不支持 transport=sdk",
            retryable=False,
        )

    try:
        key_selection = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        return TransportResult(success=False, status_code=503, error_text=str(exc), retryable=False)

    driver_name = str(getattr(driver, "name", "") or "").lower()
    upstream_style: str = "openai"
    if driver_name in ("anthropic", "claude"):
        upstream_style = "claude"

    try:
        upstream_payload = adapt_request_payload(
            payload,
            from_style=api_style,
            to_style=upstream_style,
            upstream_model_id=model_id,
        )
        sdk_payload = await call_sdk_generate_with_metrics(
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
        )
    except Exception as exc:
        record_key_failure(key_selection, retryable=True, status_code=None, redis=redis)
        return TransportResult(success=False, error_text=str(exc), retryable=True)

    record_key_success(key_selection, redis=redis)

    converted: Any = sdk_payload
    if (
        str(getattr(driver, "name", "") or "").lower() in ("google", "vertexai")
        and isinstance(sdk_payload, dict)
        and sdk_payload.get("candidates") is not None
        and _GEMINI_MODEL_REGEX.search(str(payload.get("model") or model_id or ""))
    ):
        # 先统一成 OpenAI chat payload，再交由协议适配层转换到 responses/claude 等客户端风格。
        converted = _build_openai_completion_from_gemini(
            sdk_payload,
            payload.get("model") or model_id,
        )

    try:
        converted = adapt_response_payload(
            converted,
            from_style=upstream_style,
            to_style=api_style,
            request_model=str(payload.get("model") or model_id),
        )
    except Exception:
        pass

    return TransportResult(
        success=True,
        response=JSONResponse(content=converted, status_code=200),
    )


async def execute_claude_cli_transport(
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
) -> TransportResult:
    provider_cfg = provider_config.get_provider_config(provider_id)
    if provider_cfg is None:
        return TransportResult(
            success=False,
            status_code=503,
            error_text=f"Provider '{provider_id}' is not configured",
            retryable=False,
        )

    try:
        key_selection = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        return TransportResult(success=False, status_code=503, error_text=str(exc), retryable=False)

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
        return TransportResult(
            success=False,
            status_code=500,
            error_text=f"Failed to build Claude CLI request: {exc}",
            retryable=False,
        )

    claude_url = f"{str(provider_cfg.base_url).rstrip('/')}/v1/messages?beta=true"
    try:
        r = await call_upstream_http_with_metrics(
            client=client,
            url=claude_url,
            headers=claude_cli_headers,
            json_body=claude_payload,
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
        )
    except httpx.HTTPError as exc:
        record_key_failure(key_selection, retryable=True, status_code=None, redis=redis)
        return TransportResult(success=False, error_text=str(exc), retryable=True)

    status_code = r.status_code
    text = r.text
    if status_code >= 400:
        retryable = _is_retryable_upstream_status(provider_id, status_code)
        record_key_failure(key_selection, retryable=retryable, status_code=status_code, redis=redis)
        return TransportResult(
            success=False,
            status_code=status_code,
            error_text=text,
            retryable=retryable,
        )

    record_key_success(key_selection, redis=redis)
    try:
        content: Any = r.json()
    except ValueError:
        content = {"raw": text}

    try:
        content = adapt_response_payload(
            content,
            from_style="claude",
            to_style=api_style,
            request_model=str(payload.get("model") or model_id),
        )
    except Exception as exc:
        return TransportResult(
            success=False,
            status_code=502,
            error_text=f"Failed to adapt Claude response: {exc}",
            retryable=False,
        )

    return TransportResult(
        success=True,
        response=JSONResponse(content=content, status_code=status_code),
    )


__all__ = [
    "TransportResult",
    "_build_headers",
    "execute_claude_cli_transport",
    "execute_http_transport",
    "execute_sdk_transport",
]
