from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.api.v1.chat.header_builder import build_upstream_headers
from app.logging_config import logger
from app.provider.key_pool import (
    NoAvailableProviderKey,
    SelectedProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)
from app.provider.sdk_selector import get_sdk_driver, normalize_base_url
from app.schemas import ProviderConfig
from app.services.claude_cli_transformer import (
    build_claude_cli_headers,
    transform_to_claude_cli_format,
)

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Redis = object  # type: ignore[misc,assignment]


ProbeApiStyle = Literal["auto", "openai", "claude", "responses"]


@dataclass(frozen=True)
class ProbeExecutionResult:
    success: bool
    api_style: str
    status_code: int | None
    latency_ms: int | None
    error_message: str | None
    response_text: str | None
    response_excerpt: str | None
    response_json: Any | None


def _retryable_status(status_code: int | None) -> bool:
    if status_code is None:
        return True
    if status_code >= 500:
        return True
    return status_code in (408, 409, 425, 429)


def _pick_api_style(cfg: ProviderConfig, requested: ProbeApiStyle) -> str:
    if requested != "auto":
        return requested

    declared = {str(item).lower() for item in (cfg.supported_api_styles or []) if item}
    if declared:
        if "openai" in declared:
            return "openai"
        if "responses" in declared:
            return "responses"
        if "claude" in declared:
            return "claude"
        return "openai"

    if getattr(cfg, "chat_completions_path", None):
        return "openai"
    if getattr(cfg, "responses_path", None):
        return "responses"
    if getattr(cfg, "messages_path", None):
        return "claude"
    return "openai"


def _build_url(cfg: ProviderConfig, api_style: str) -> str:
    base = str(cfg.base_url).rstrip("/")
    if api_style == "claude":
        path = getattr(cfg, "messages_path", None) or "/v1/messages"
    elif api_style == "responses":
        path = getattr(cfg, "responses_path", None) or "/v1/responses"
    else:
        path = getattr(cfg, "chat_completions_path", None) or "/v1/chat/completions"
    trimmed = str(path).strip()
    if not trimmed.startswith("/"):
        trimmed = "/" + trimmed
    return f"{base}{trimmed}"


def _build_probe_payload(api_style: str, *, model_id: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    if api_style == "claude":
        return {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }

    if api_style == "responses":
        return {
            "model": model_id,
            "input": [{"role": "user", "content": prompt}],
            "max_output_tokens": max_tokens,
            "temperature": 0,
        }

    return {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
    }


def _extract_openai_text(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    msg = first.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"]
    text = first.get("text")
    if isinstance(text, str):
        return text
    return None


def _extract_claude_text(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join([p for p in parts if p]) or None
    return None


def _extract_responses_text(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    output = payload.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            if parts:
                return "".join(parts)
    return None


def _extract_response_text(api_style: str, payload: Any) -> str | None:
    if api_style == "claude":
        return _extract_claude_text(payload)
    if api_style == "responses":
        return _extract_responses_text(payload)
    return _extract_openai_text(payload)


def _dump_excerpt(text: str | None, limit: int = 4000) -> str | None:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


async def execute_user_probe(
    client: httpx.AsyncClient,
    *,
    provider_cfg: ProviderConfig,
    model_id: str,
    prompt: str,
    max_tokens: int,
    api_style: ProbeApiStyle = "auto",
    redis: Redis | None = None,
) -> ProbeExecutionResult:
    """
    执行一次用户探针对话请求（真实请求上游）。

    - HTTP transport: 直接调用上游对话接口（chat.completions / messages / responses）。
    - sdk transport: 使用官方 SDK 发起对话请求。
    - claude_cli transport: 使用 Claude Code CLI 伪装格式，POST /v1/messages?beta=true。
    """
    transport = getattr(provider_cfg, "transport", "http") or "http"
    chosen_style = _pick_api_style(provider_cfg, api_style)

    try:
        selection: SelectedProviderKey = await acquire_provider_key(provider_cfg, redis)
    except NoAvailableProviderKey as exc:
        return ProbeExecutionResult(
            success=False,
            api_style=chosen_style,
            status_code=None,
            latency_ms=None,
            error_message=str(exc),
            response_text=None,
            response_excerpt=None,
            response_json=None,
        )

    start = time.perf_counter()
    status_code: int | None = None
    raw_text: str | None = None
    parsed_json: Any | None = None

    try:
        if transport == "sdk":
            driver = get_sdk_driver(provider_cfg)
            if driver is None:
                raise RuntimeError("transport=sdk 但未配置可用的 sdk_vendor")

            sdk_payload = _build_probe_payload(
                "claude" if driver.name == "claude" else "openai",
                model_id=model_id,
                prompt=prompt,
                max_tokens=max_tokens,
            )
            parsed_json = await driver.generate_content(
                api_key=selection.key,
                model_id=model_id,
                payload=sdk_payload,
                base_url=normalize_base_url(provider_cfg.base_url),
            )
            status_code = 200
        elif transport == "claude_cli":
            claude_cli_headers = build_claude_cli_headers(selection.key)
            openai_payload = _build_probe_payload(
                "openai",
                model_id=model_id,
                prompt=prompt,
                max_tokens=max_tokens,
            )
            claude_payload = transform_to_claude_cli_format(
                openai_payload,
                api_key=selection.key,
                session_id=None,
            )
            url = f"{str(provider_cfg.base_url).rstrip('/')}/v1/messages?beta=true"
            resp = await client.post(url, headers=claude_cli_headers, json=claude_payload)
            status_code = resp.status_code
            raw_text = resp.text
            try:
                parsed_json = resp.json()
            except ValueError:
                parsed_json = None
        else:
            headers = build_upstream_headers(
                selection.key,
                provider_cfg,
                call_style=chosen_style,
                is_stream=False,
            )

            url = _build_url(provider_cfg, chosen_style)
            payload = _build_probe_payload(
                chosen_style, model_id=model_id, prompt=prompt, max_tokens=max_tokens
            )
            resp = await client.post(url, headers=headers, json=payload)
            status_code = resp.status_code
            raw_text = resp.text
            try:
                parsed_json = resp.json()
            except ValueError:
                parsed_json = None
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000.0)
        record_key_failure(selection, retryable=True, status_code=status_code, redis=redis)
        logger.warning(
            "user_probe: upstream error provider=%s transport=%s style=%s model=%s err=%s",
            provider_cfg.id,
            transport,
            chosen_style,
            model_id,
            exc,
        )
        return ProbeExecutionResult(
            success=False,
            api_style=chosen_style,
            status_code=status_code,
            latency_ms=duration_ms,
            error_message=str(exc),
            response_text=None,
            response_excerpt=_dump_excerpt(raw_text),
            response_json=None,
        )

    duration_ms = int((time.perf_counter() - start) * 1000.0)

    if status_code is None:
        record_key_failure(selection, retryable=True, status_code=None, redis=redis)
        return ProbeExecutionResult(
            success=False,
            api_style=chosen_style,
            status_code=None,
            latency_ms=duration_ms,
            error_message="unknown_status",
            response_text=None,
            response_excerpt=_dump_excerpt(raw_text),
            response_json=parsed_json,
        )

    if status_code >= 400:
        record_key_failure(
            selection,
            retryable=_retryable_status(status_code),
            status_code=status_code,
            redis=redis,
        )
        return ProbeExecutionResult(
            success=False,
            api_style=chosen_style,
            status_code=status_code,
            latency_ms=duration_ms,
            error_message=f"HTTP {status_code}",
            response_text=_extract_response_text(chosen_style, parsed_json),
            response_excerpt=_dump_excerpt(raw_text),
            response_json=parsed_json,
        )

    record_key_success(selection, redis=redis)
    return ProbeExecutionResult(
        success=True,
        api_style=chosen_style,
        status_code=status_code,
        latency_ms=duration_ms,
        error_message=None,
        response_text=_extract_response_text(chosen_style, parsed_json),
        response_excerpt=_dump_excerpt(raw_text),
        response_json=parsed_json,
    )


__all__ = ["ProbeApiStyle", "ProbeExecutionResult", "execute_user_probe"]
