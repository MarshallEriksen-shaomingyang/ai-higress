"""Core chat routing helpers extracted from app.routes.

This module contains response models and utility functions used by the
chat/completions-style endpoints so that the main routes module can stay thin.
"""

# Export all public symbols for wildcard import in app.routes
__all__ = [
    # Response models
    "HealthResponse",
    "ModelInfo",
    "ModelsResponse",
    # Exception classes
    "ClaudeMessagesFallbackStreamError",
    "ResponsesFallbackStreamError",
    # Stream adapters
    "GeminiToOpenAIStreamAdapter",
    "OpenAIToClaudeStreamAdapter",
    # Private functions (explicitly exported for app.routes)
    "_get_or_fetch_models",
    "_normalize_payload_by_model",
    "_strip_model_group_prefix",
    "_build_ordered_candidates",
    "_is_retryable_upstream_status",
    "_apply_upstream_path_override",
    "_enforce_allowed_providers",
    "_build_provider_headers",
    "_send_claude_fallback_non_stream",
    "_send_responses_fallback_non_stream",
    "_claude_streaming_fallback_iterator",
    "_responses_streaming_fallback_iterator",
    "_load_metrics_for_candidates",
    "_build_dynamic_logical_model_for_group",
    "_adapt_responses_payload",
    "_chat_to_responses_payload",
    "_wrap_chat_stream_response",
    "_should_attempt_claude_messages_fallback",
    "_build_openai_completion_from_gemini",
    "_encode_sse_payload",
    "_GEMINI_MODEL_REGEX",
]

import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthenticatedAPIKey
from app.context_store import save_context
from app.logging_config import logger
from app.model_cache import get_models_from_cache, set_models_cache
from app.models import Provider, ProviderModel
from app.provider.config import (
    get_provider_config,
    load_provider_configs,
    load_providers_with_configs,
)
from app.provider.discovery import ensure_provider_models_cached
from app.provider.key_pool import (
    SelectedProviderKey,
    acquire_provider_key,
)
from app.routing.exceptions import NoAllowedProvidersAvailable
from app.routing.scheduler import CandidateScore
from app.schemas import (
    LogicalModel,
    ModelCapability,
    PhysicalModel,
    ProviderConfig,
    RoutingMetrics,
)
from app.services.metrics_service import (
    call_upstream_http_with_metrics,
    stream_upstream_with_metrics,
)
from app.settings import settings
from app.storage.redis_service import get_routing_metrics
from app.upstream import UpstreamStreamError


class HealthResponse(BaseModel):
    status: str = "ok"


class ModelInfo(BaseModel):
    id: str
    object: str | None = None
    created: int | None = None
    owned_by: str | None = None


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo] = Field(default_factory=list)


def _enforce_allowed_providers(
    candidates: list[PhysicalModel],
    api_key: AuthenticatedAPIKey,
) -> list[PhysicalModel]:
    if not api_key.has_provider_restrictions:
        return candidates
    allowed = set(api_key.allowed_provider_ids)
    filtered = [cand for cand in candidates if cand.provider_id in allowed]
    if not filtered:
        raise NoAllowedProvidersAvailable(str(api_key.id), api_key.allowed_provider_ids)
    return filtered


def _apply_upstream_path_override(endpoint: str, override_path: str | None) -> str:
    """
    Replace the path portion of an upstream endpoint when an override is required.
    """
    if not override_path:
        return endpoint

    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return endpoint

    normalized = override_path if override_path.startswith("/") else f"/{override_path}"
    return urlunsplit((parsed.scheme, parsed.netloc, normalized, "", ""))


@dataclass
class ProviderEndpointSelection:
    url: str
    api_style: str


_STYLE_PRIORITY: dict[str, list[str]] = {
    "responses": ["responses", "openai"],
    "claude": ["claude", "openai"],
    "openai": ["openai", "claude"],
}


def _provider_supports_api_style(cfg: ProviderConfig, style: str) -> bool:
    # When supported_api_styles is explicitly configured, it is treated as the
    # authoritative declaration of what this provider supports. Only when it
    # is empty do we fall back to heuristics based on configured paths.
    declared = {str(item).lower() for item in (cfg.supported_api_styles or []) if item}
    if declared:
        return style in declared
    if style == "responses":
        return bool(getattr(cfg, "responses_path", None))
    if style == "claude":
        return bool(getattr(cfg, "messages_path", None))
    return True


def _path_for_api_style(cfg: ProviderConfig, style: str) -> str | None:
    if style == "responses":
        path = getattr(cfg, "responses_path", None)
        return path if path else None
    if style == "claude":
        path = getattr(cfg, "messages_path", None)
        return path if path else None
    path = getattr(cfg, "chat_completions_path", None)
    return path if path else "/v1/chat/completions"


def _select_provider_endpoint(
    cfg: ProviderConfig, requested_style: str
) -> ProviderEndpointSelection | None:
    transport = getattr(cfg, "transport", "http")
    if transport == "sdk":
        return ProviderEndpointSelection(
            url=str(cfg.base_url).rstrip("/"),
            api_style="openai",
        )

    priorities = _STYLE_PRIORITY.get(requested_style, ["openai"])
    base = str(cfg.base_url).rstrip("/")

    for style in priorities:
        if not _provider_supports_api_style(cfg, style):
            continue
        path = _path_for_api_style(cfg, style)
        if not path:
            continue
        trimmed = path.strip()
        if not trimmed:
            continue
        if not trimmed.startswith("/"):
            trimmed = "/" + trimmed
        return ProviderEndpointSelection(url=f"{base}{trimmed}", api_style=style)
    return None


async def _build_provider_headers(
    provider_cfg: ProviderConfig, redis, api_style: str = "openai"
) -> tuple[dict[str, str], SelectedProviderKey]:
    """
    Build headers for calling a concrete provider upstream.

    This reuses the browser-mimic settings (User-Agent / Origin / Referer)
    but replaces the Authorization header with a selected provider-specific API key.
    
    Args:
        provider_cfg: Provider configuration
        redis: Redis connection
        api_style: API style ("openai", "claude", etc.) to determine auth header format
    
    Returns:
        Tuple of (headers dict, key selection)
    """
    key_selection = await acquire_provider_key(provider_cfg, redis)

    # Choose authentication header format based on API style
    headers: dict[str, str] = {"Accept": "application/json"}

    if api_style == "claude":
        # Claude API uses x-api-key header
        headers["x-api-key"] = key_selection.key
        logger.debug(
            "build_provider_headers: using Claude auth format (x-api-key) for provider=%s",
            provider_cfg.id,
        )
    else:
        # OpenAI and most other APIs use Authorization: Bearer
        headers["Authorization"] = f"Bearer {key_selection.key}"
        logger.debug(
            "build_provider_headers: using OpenAI auth format (Authorization: Bearer) for provider=%s",
            provider_cfg.id,
        )

    # Optional browser-mimic behaviour.
    if settings.mask_as_browser:
        headers["User-Agent"] = settings.mask_user_agent
        if settings.mask_origin:
            headers["Origin"] = settings.mask_origin
        if settings.mask_referer:
            headers["Referer"] = settings.mask_referer

    # Provider-specific extra headers take precedence.
    if provider_cfg.custom_headers:
        headers.update(provider_cfg.custom_headers)

    return headers, key_selection


@dataclass
class FallbackOutcome:
    response: Any | None = None
    retryable: bool = False
    status_code: int | None = None
    error_text: str | None = None


class ClaudeMessagesFallbackStreamError(Exception):
    def __init__(
        self,
        *,
        status_code: int | None,
        text: str,
        retryable: bool,
    ) -> None:
        super().__init__(text)
        self.status_code = status_code
        self.text = text
        self.retryable = retryable


class ResponsesFallbackStreamError(Exception):
    def __init__(
        self,
        *,
        status_code: int | None,
        text: str,
        retryable: bool,
    ) -> None:
        super().__init__(text)
        self.status_code = status_code
        self.text = text
        self.retryable = retryable


def _build_chat_completions_fallback_url(endpoint: str) -> str | None:
    if not endpoint:
        return None
    return _apply_upstream_path_override(endpoint, "/v1/chat/completions")


def _claude_content_blocks_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        segments: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            text_value = block.get("text")
            if isinstance(text_value, str):
                segments.append(text_value)
                continue
            if block_type == "tool_use" and block.get("input") is not None:
                segments.append(json.dumps(block["input"], ensure_ascii=False))
            elif block_type == "tool_result" and isinstance(block.get("content"), list):
                for part in block["content"]:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        segments.append(part["text"])
        return "\n".join(seg for seg in segments if seg)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


def _claude_messages_to_openai_chat_payload(
    payload: dict[str, Any],
    *,
    upstream_model_id: str | None,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    system_prompt = payload.get("system")
    if isinstance(system_prompt, str) and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    elif isinstance(system_prompt, list):
        joined = "\n".join(str(item) for item in system_prompt if item)
        if joined:
            messages.append({"role": "system", "content": joined})

    for msg in payload.get("messages", []):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or "user"
        content_text = _claude_content_blocks_to_text(msg.get("content"))
        messages.append({"role": role, "content": content_text})

    if not messages:
        messages.append({"role": "user", "content": ""})

    converted: dict[str, Any] = {
        "model": upstream_model_id or payload.get("model"),
        "messages": messages,
    }

    if payload.get("stream") is True:
        converted["stream"] = True

    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
        if payload.get(key) is not None:
            converted[key] = payload[key]

    stop_sequences = payload.get("stop_sequences") or payload.get("stop")
    if stop_sequences:
        converted["stop"] = stop_sequences

    if payload.get("max_tokens") is not None:
        converted["max_tokens"] = payload["max_tokens"]
    elif payload.get("max_tokens_to_sample") is not None:
        converted["max_tokens"] = payload["max_tokens_to_sample"]

    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("user"):
        converted["user"] = str(metadata["user"])

    return converted


def _openai_content_to_claude_segments(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        segments: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text_value = item.get("text")
            if isinstance(text_value, str):
                segments.append({"type": "text", "text": text_value})
        return segments
    return []


def _openai_usage_to_claude_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return usage if usage is None else None
    return {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def _map_openai_finish_reason(finish_reason: str | None) -> str | None:
    if finish_reason is None:
        return None
    mapping = {"stop": "end_turn", "length": "max_tokens"}
    return mapping.get(finish_reason, finish_reason)


def _openai_chat_to_claude_response(
    openai_payload: dict[str, Any],
    *,
    request_model: str | None,
) -> dict[str, Any]:
    response_id = openai_payload.get("id") or f"msg_{uuid.uuid4().hex}"
    created = openai_payload.get("created") or int(time.time())
    choices = openai_payload.get("choices")
    first_choice: dict[str, Any] = {}
    if isinstance(choices, list) and choices:
        candidate = choices[0]
        if isinstance(candidate, dict):
            first_choice = candidate
    message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
    segments = _openai_content_to_claude_segments(message.get("content"))
    if not segments:
        text_value = message.get("content")
        if isinstance(text_value, str):
            segments = [{"type": "text", "text": text_value}]
        else:
            segments = [{"type": "text", "text": ""}]

    return {
        "id": response_id,
        "type": "message",
        "role": message.get("role") or "assistant",
        "model": request_model or openai_payload.get("model"),
        "content": segments,
        "stop_reason": _map_openai_finish_reason(first_choice.get("finish_reason")),
        "stop_sequence": None,
        "usage": _openai_usage_to_claude_usage(openai_payload.get("usage")),
        "created": created,
    }


def _should_attempt_claude_messages_fallback(
    *,
    api_style: str,
    upstream_path_override: str | None,
    status_code: int | None,
    response_text: str | None,
) -> bool:
    if api_style != "claude":
        return False
    if not upstream_path_override:
        return False
    normalized_path = upstream_path_override.lower()
    if "message" not in normalized_path:
        return False
    if status_code == 404:
        return True
    if status_code in (400, 405):
        text = (response_text or "").lower()
        markers = ["invalid url", "not found", "/v1/message", "unknown path"]
        return any(marker in text for marker in markers)
    return False


class OpenAIToClaudeStreamAdapter:
    def __init__(self, model: str | None) -> None:
        self.model = model
        self.message_id = f"msg_{uuid.uuid4().hex}"
        self.content_block_id = f"{self.message_id}-cb-0"
        self.buffer = ""
        self.started = False
        self.had_error = False
        self.stop_reason: str | None = None
        self.usage: dict[str, Any] | None = None
        self.aggregate_text: str = ""
        self.tool_block_seq = 1  # 0 号被文本 block 占用

    def _usage_object(self) -> dict[str, int]:
        """
        Claude messages SSE 事件里 `usage` 字段在部分客户端（如 Claude Code CLI）
        的 schema 校验中是必填 object，不能为 null。
        """
        usage = self.usage if isinstance(self.usage, dict) else {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return {
            "input_tokens": int(input_tokens) if isinstance(input_tokens, int) else 0,
            "output_tokens": int(output_tokens) if isinstance(output_tokens, int) else 0,
        }

    def _encode_event(self, event: str, payload: dict[str, Any]) -> bytes:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()

    def _emit_start_events(self) -> list[bytes]:
        self.started = True
        message_payload = {
            "type": "message_start",
            "message": {
                "id": self.message_id,
                "type": "message",
                "role": "assistant",
                "model": self.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": self._usage_object(),
            },
        }
        content_block_payload = {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "id": self.content_block_id,
                "type": "text",
                "text": "",
            },
        }
        return [
            self._encode_event("message_start", message_payload),
            self._encode_event("content_block_start", content_block_payload),
        ]

    def _extract_text_delta(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
            return "".join(parts)
        return ""

    def process_chunk(self, chunk: bytes) -> list[bytes]:
        outputs: list[bytes] = []
        try:
            decoded = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return outputs
        if self.had_error:
            return outputs
        self.buffer += decoded
        while "\n\n" in self.buffer:
            raw_event, self.buffer = self.buffer.split("\n\n", 1)
            raw_event = raw_event.strip()
            if not raw_event.startswith("data:"):
                continue
            payload_str = raw_event[len("data:") :].strip()
            if not payload_str:
                continue
            if payload_str == "[DONE]":
                continue
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("error") is not None:
                err = data.get("error")
                message = None
                if isinstance(err, dict):
                    raw_message = err.get("message")
                    if isinstance(raw_message, str) and raw_message.strip():
                        message = raw_message.strip()
                    else:
                        message = json.dumps(err, ensure_ascii=False)
                elif isinstance(err, str) and err.strip():
                    message = err.strip()
                else:
                    message = "Upstream streaming error"
                self.had_error = True
                outputs.append(
                    self._encode_event(
                        "error",
                        {
                            "type": "error",
                            "error": {
                                "type": "upstream_error",
                                "message": message,
                            },
                        },
                    )
                )
                return outputs
            choices = data.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta") or {}
                text_delta = self._extract_text_delta(delta.get("content"))
                if text_delta:
                    if not self.started:
                        outputs.extend(self._emit_start_events())
                    self.aggregate_text += text_delta
                    outputs.append(
                        self._encode_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {"type": "text_delta", "text": text_delta},
                            },
                        )
                    )
                tool_deltas = delta.get("tool_calls")
                if isinstance(tool_deltas, list):
                    for tc in tool_deltas:
                        if not isinstance(tc, dict):
                            continue
                        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                        name = fn.get("name") or f"tool_{self.tool_block_seq}"
                        args_delta = fn.get("arguments") or ""
                        block_id = tc.get("id") or f"tool_{self.tool_block_seq}"
                        if not self.started:
                            outputs.extend(self._emit_start_events())
                        # tool_use start
                        outputs.append(
                            self._encode_event(
                                "content_block_start",
                                {
                                    "type": "content_block_start",
                                    "index": self.tool_block_seq,
                                    "content_block": {
                                        "id": block_id,
                                        "type": "tool_use",
                                        "name": name,
                                        "input": {},
                                    },
                                },
                            )
                        )
                        if args_delta:
                            outputs.append(
                                self._encode_event(
                                    "content_block_delta",
                                    {
                                        "type": "content_block_delta",
                                        "index": self.tool_block_seq,
                                        "delta": {
                                            "type": "input_json_delta",
                                            "partial_json": args_delta,
                                            "tool_use_id": block_id,
                                        },
                                    },
                                )
                            )
                        outputs.append(
                            self._encode_event(
                                "content_block_stop",
                                {"type": "content_block_stop", "index": self.tool_block_seq},
                            )
                        )
                        self.tool_block_seq += 1
                finish_reason = choice.get("finish_reason")
                if isinstance(finish_reason, str):
                    self.stop_reason = _map_openai_finish_reason(finish_reason)
            usage = data.get("usage")
            if isinstance(usage, dict):
                self.usage = _openai_usage_to_claude_usage(usage)
        return outputs

    def finalize(self) -> list[bytes]:
        outputs: list[bytes] = []
        if self.had_error:
            return outputs
        if not self.started:
            outputs.extend(self._emit_start_events())
        outputs.append(
            self._encode_event("content_block_stop", {"type": "content_block_stop", "index": 0})
        )
        outputs.append(
            self._encode_event(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": self.stop_reason or "end_turn",
                        "stop_sequence": None,
                    },
                    "usage": self._usage_object(),
                },
            )
        )
        outputs.append(
            self._encode_event(
                "message_stop",
                {
                    "type": "message_stop",
                },
            )
        )
        return outputs


async def _send_claude_fallback_non_stream(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    provider_id: str,
    model_id: str,
    logical_model_id: str,
    payload: dict[str, Any],
    fallback_url: str | None,
    redis,
    x_session_id: str | None,
    bind_session,
    db: Session,
    user_id: UUID | None,
    api_key_id: UUID | None,
) -> FallbackOutcome:
    if not fallback_url:
        return FallbackOutcome(
            response=None,
            retryable=False,
            status_code=None,
            error_text="Claude fallback URL unavailable",
        )
    logger.info(
        "claude_fallback: retrying via chat.completions (provider=%s model=%s url=%s)",
        provider_id,
        model_id,
        fallback_url,
    )
    fallback_payload = _claude_messages_to_openai_chat_payload(
        payload, upstream_model_id=model_id
    )
    try:
        response = await call_upstream_http_with_metrics(
            client=client,
            url=fallback_url,
            headers=headers,
            json_body=fallback_payload,
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=user_id,
            api_key_id=api_key_id,
        )
    except httpx.HTTPError as exc:
        return FallbackOutcome(
            response=None, retryable=True, status_code=None, error_text=str(exc)
        )

    text = response.text
    status_code = response.status_code

    if status_code >= 400:
        return FallbackOutcome(
            response=None,
            retryable=_is_retryable_upstream_status(provider_id, status_code),
            status_code=status_code,
            error_text=text,
        )

    await bind_session(provider_id, model_id)
    await save_context(redis, x_session_id, payload, text)

    try:
        payload_json = response.json()
    except ValueError:
        payload_json = None

    if not isinstance(payload_json, dict):
        return FallbackOutcome(
            response=JSONResponse(content={"raw": text}, status_code=status_code)
        )

    claude_payload = _openai_chat_to_claude_response(
        payload_json, request_model=payload.get("model") or model_id
    )
    return FallbackOutcome(
        response=JSONResponse(content=claude_payload, status_code=status_code)
    )


async def _send_responses_fallback_non_stream(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    provider_id: str,
    model_id: str,
    logical_model_id: str,
    payload: dict[str, Any],
    target_url: str,
    redis,
    x_session_id: str | None,
    bind_session,
    db: Session,
    user_id: UUID | None,
    api_key_id: UUID | None,
) -> FallbackOutcome:
    if not target_url:
        return FallbackOutcome(
            response=None,
            retryable=False,
            status_code=None,
            error_text="Responses fallback URL unavailable",
        )
    logger.info(
        "responses_fallback: forwarding via chat.completions (provider=%s model=%s url=%s)",
        provider_id,
        model_id,
        target_url,
    )
    fallback_payload = _adapt_responses_payload(payload)
    fallback_payload["model"] = model_id
    try:
        response = await call_upstream_http_with_metrics(
            client=client,
            url=target_url,
            headers=headers,
            json_body=fallback_payload,
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=user_id,
            api_key_id=api_key_id,
        )
    except httpx.HTTPError as exc:
        return FallbackOutcome(
            response=None,
            retryable=True,
            status_code=None,
            error_text=str(exc),
        )

    text = response.text
    status_code = response.status_code
    if status_code >= 400:
        return FallbackOutcome(
            response=None,
            retryable=_is_retryable_upstream_status(provider_id, status_code),
            status_code=status_code,
            error_text=text,
        )

    await bind_session(provider_id, model_id)
    await save_context(redis, x_session_id, payload, text)

    try:
        payload_json = response.json()
    except ValueError:
        payload_json = None

    if isinstance(payload_json, dict):
        converted = _chat_to_responses_payload(payload_json)
        return FallbackOutcome(
            response=JSONResponse(content=converted, status_code=status_code)
        )

    return FallbackOutcome(
        response=JSONResponse(content={"raw": text}, status_code=status_code)
    )


async def _claude_streaming_fallback_iterator(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    provider_id: str,
    model_id: str,
    logical_model_id: str,
    fallback_url: str | None,
    payload: dict[str, Any],
    redis,
    session_id: str | None,
    bind_session_cb,
    db: Session,
    user_id: UUID | None,
    api_key_id: UUID | None,
) -> AsyncIterator[bytes]:
    if not fallback_url:
        raise ClaudeMessagesFallbackStreamError(
            status_code=None, text="Claude fallback URL unavailable", retryable=False
        )
    logger.info(
        "claude_fallback: streaming via chat.completions (provider=%s model=%s url=%s)",
        provider_id,
        model_id,
        fallback_url,
    )
    fallback_payload = _claude_messages_to_openai_chat_payload(
        payload, upstream_model_id=model_id
    )
    adapter = OpenAIToClaudeStreamAdapter(payload.get("model") or model_id)
    first_chunk = True
    try:
        async for chunk in stream_upstream_with_metrics(
            client=client,
            method="POST",
            url=fallback_url,
            headers=headers,
            json_body=fallback_payload,
            redis=redis,
            session_id=session_id,
            sse_style="openai",
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=user_id,
            api_key_id=api_key_id,
        ):
            if first_chunk:
                first_chunk = False
                await bind_session_cb(provider_id, model_id)
            for converted in adapter.process_chunk(chunk):
                yield converted
    except UpstreamStreamError as err:
        raise ClaudeMessagesFallbackStreamError(
            status_code=err.status_code,
            text=err.text,
            retryable=_is_retryable_upstream_status(provider_id, err.status_code),
        ) from err

    for tail in adapter.finalize():
        yield tail


async def _responses_streaming_fallback_iterator(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    provider_id: str,
    model_id: str,
    logical_model_id: str,
    target_url: str,
    payload: dict[str, Any],
    redis,
    session_id: str | None,
    bind_session_cb,
    db: Session,
    user_id: UUID | None,
    api_key_id: UUID | None,
) -> AsyncIterator[bytes]:
    if not target_url:
        raise ResponsesFallbackStreamError(
            status_code=None, text="Responses fallback URL unavailable", retryable=False
        )
    logger.info(
        "responses_fallback: streaming via chat.completions (provider=%s model=%s url=%s)",
        provider_id,
        model_id,
        target_url,
    )
    fallback_payload = _adapt_responses_payload(payload)
    fallback_payload["model"] = model_id

    # Create a buffer to collect all chunks from upstream
    buffer = ""
    index_to_text: dict[int, str] = {}
    response_id: str | None = None
    model_name: str | None = None
    created: int | None = None
    usage: dict[str, Any] | None = None
    created_emitted = False
    first_chunk = True

    try:
        async for chunk in stream_upstream_with_metrics(
            client=client,
            method="POST",
            url=target_url,
            headers=headers,
            json_body=fallback_payload,
            redis=redis,
            session_id=session_id,
            sse_style="openai",
            db=db,
            provider_id=provider_id,
            logical_model=logical_model_id,
            user_id=user_id,
            api_key_id=api_key_id,
        ):
            if first_chunk:
                first_chunk = False
                await bind_session_cb(provider_id, model_id)

            # Process chat completion chunks and convert to responses format
            try:
                decoded = chunk.decode("utf-8")
            except UnicodeDecodeError:
                continue

            buffer += decoded
            while "\n\n" in buffer:
                raw_event, buffer = buffer.split("\n\n", 1)
                raw_event = raw_event.strip()
                if not raw_event.startswith("data:"):
                    continue
                payload_str = raw_event[len("data:") :].strip()
                if not payload_str:
                    continue

                if payload_str == "[DONE]":
                    # Emit response.created if not yet emitted
                    if not created_emitted:
                        rid = _ensure_response_id(response_id)
                        response_id = rid
                        created_payload = _build_created_event_payload(rid, model_name, created)
                        yield _encode_sse_payload(created_payload)
                        created_emitted = True

                    # Emit output done events
                    for idx in sorted(index_to_text):
                        rid = _ensure_response_id(response_id)
                        yield _encode_sse_payload(_build_output_done_event_payload(rid, idx))

                    # Emit completed event
                    rid = _ensure_response_id(response_id)
                    completed = _build_completed_event_payload(
                        rid, model_name, created, index_to_text, usage
                    )
                    yield _encode_sse_payload(completed)
                    yield b"data: [DONE]\n\n"
                    return

                try:
                    data = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue

                if data.get("object") != "chat.completion.chunk":
                    continue

                if isinstance(data.get("id"), str):
                    response_id = response_id or data["id"]
                model_name = model_name or data.get("model")
                created = created or data.get("created")
                if data.get("usage"):
                    usage = data["usage"]

                for choice in data.get("choices", []):
                    if not isinstance(choice, dict):
                        continue
                    idx = choice.get("index", 0)
                    delta = choice.get("delta") or {}
                    delta_content = delta.get("content")
                    text_delta = _flatten_responses_content(delta_content)

                    if text_delta:
                        existing = index_to_text.get(idx, "")
                        index_to_text[idx] = existing + text_delta

                        # Emit created event on first content
                        if not created_emitted:
                            rid = _ensure_response_id(response_id)
                            response_id = rid
                            created_payload = _build_created_event_payload(rid, model_name, created)
                            yield _encode_sse_payload(created_payload)
                            created_emitted = True

                        # Emit delta event
                        rid = _ensure_response_id(response_id)
                        yield _encode_sse_payload({
                            "id": rid,
                            "type": "response.output_text.delta",
                            "response_id": rid,
                            "output_index": idx,
                            "delta": text_delta,
                        })

    except UpstreamStreamError as err:
        raise ResponsesFallbackStreamError(
            status_code=err.status_code,
            text=err.text,
            retryable=_is_retryable_upstream_status(provider_id, err.status_code),
        ) from err

    chat_response = StreamingResponse(upstream_iterator(), media_type="text/event-stream")
    wrapped = _wrap_chat_stream_response(chat_response)
    first_chunk = True
    try:
        async for chunk in wrapped.body_iterator:
            if first_chunk:
                first_chunk = False
                await bind_session_cb(provider_id, model_id)
            yield chunk
    except UpstreamStreamError as err:
        raise ResponsesFallbackStreamError(
            status_code=err.status_code,
            text=err.text,
            retryable=_is_retryable_upstream_status(provider_id, err.status_code),
        ) from err


def _inline_data_to_data_url(inline: Any) -> str | None:
    if not isinstance(inline, dict):
        return None
    data = inline.get("data")
    mime = inline.get("mimeType") or "application/octet-stream"
    if isinstance(data, str) and data:
        return f"data:{mime};base64,{data}"
    return None


def _convert_gemini_content_to_segments(content: Any) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            inline_url = _inline_data_to_data_url(item.get("inlineData"))
            if inline_url:
                segments.append({"type": "image_url", "image_url": {"url": inline_url}})
            text_val = item.get("text")
            if isinstance(text_val, str):
                segments.append({"type": "text", "text": text_val})
            parts = item.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    _walk(part)
        elif isinstance(item, list):
            for sub in item:
                _walk(sub)
        elif isinstance(item, str):
            segments.append({"type": "text", "text": item})

    _walk(content)
    return segments


def _segments_to_plain_text(segments: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for seg in segments:
        if seg.get("type") == "text":
            text_val = seg.get("text")
            if isinstance(text_val, str):
                texts.append(text_val)
    return "".join(texts)


def _convert_gemini_usage_to_openai(source: dict[str, Any]) -> dict[str, Any]:
    usage = source.get("usageMetadata") or {}
    if not isinstance(usage, dict):
        return {}
    mapped = {
        "prompt_tokens": usage.get("promptTokenCount") or usage.get("promptTokens"),
        "completion_tokens": usage.get("candidatesTokenCount")
        or usage.get("completionTokens"),
        "total_tokens": usage.get("totalTokenCount") or usage.get("totalTokens"),
    }
    return {k: v for k, v in mapped.items() if v is not None}


def _build_openai_completion_from_gemini(
    payload: dict[str, Any],
    model: str | None,
) -> dict[str, Any]:
    response_id = payload.get("id") or _ensure_response_id(None)
    created_ts = int(time.time())
    create_time = payload.get("createTime") or payload.get("created")
    if isinstance(create_time, (int, float)):
        created_ts = int(create_time)
    choices: list[dict[str, Any]] = []
    candidates = payload.get("candidates") or []
    if isinstance(candidates, list):
        for idx, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                continue
            content = cand.get("content")
            segments = _convert_gemini_content_to_segments(content)
            has_non_text = any(seg.get("type") != "text" for seg in segments)
            if has_non_text and segments:
                message_content: Any = segments
            else:
                message_content = _segments_to_plain_text(segments)
            finish_reason = cand.get("finishReason")
            if isinstance(finish_reason, str):
                finish_reason = finish_reason.lower()
            choices.append(
                {
                    "index": idx,
                    "message": {"role": "assistant", "content": message_content},
                    "finish_reason": finish_reason or "stop",
                }
            )
    completion = {
        "id": response_id,
        "object": "chat.completion",
        "created": created_ts or int(time.time()),
        "model": model,
        "choices": choices,
        "usage": _convert_gemini_usage_to_openai(payload),
    }
    return completion


class GeminiToOpenAIStreamAdapter:
    def __init__(self, model: str | None) -> None:
        self.model = model
        self.response_id = _ensure_response_id(None)
        self.created = int(time.time())
        self.buffer = ""
        self.done = False
        self.index_to_text: dict[int, str] = {}

    def _build_chunk_payload(
        self,
        *,
        index: int,
        text_delta: str | None = None,
        finish_reason: str | None = None,
        segments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        choice: dict[str, Any] = {
            "index": index,
        }
        new_delta: dict[str, Any] = {}
        if segments is not None:
            new_delta["content"] = segments
        elif text_delta:
            new_delta["content"] = text_delta
        choice["delta"] = new_delta
        if new_delta:
            choice["delta"] = new_delta
        if finish_reason:
            choice["finish_reason"] = finish_reason
        return {
            "id": self.response_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [choice],
        }

    def process_chunk(self, chunk: bytes) -> list[bytes]:
        outputs: list[bytes] = []
        try:
            decoded = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return outputs
        self.buffer += decoded
        while "\n\n" in self.buffer:
            raw_event, self.buffer = self.buffer.split("\n\n", 1)
            raw_event = raw_event.strip()
            if not raw_event.startswith("data:"):
                continue
            payload_str = raw_event[len("data:") :].strip()
            if not payload_str:
                continue
            if payload_str == "[DONE]":
                outputs.append(b"data: [DONE]\n\n")
                self.done = True
                continue
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError:
                continue
            candidates = data.get("candidates") or []
            if not isinstance(candidates, list):
                continue
            for idx, cand in enumerate(candidates):
                if not isinstance(cand, dict):
                    continue
                content = cand.get("content")
                segments = _convert_gemini_content_to_segments(content)
                has_non_text = any(seg.get("type") != "text" for seg in segments)
                if has_non_text and segments:
                    outputs.append(
                        _encode_sse_payload(
                            self._build_chunk_payload(index=idx, segments=segments)
                        )
                    )
                else:
                    text_delta = _segments_to_plain_text(segments)
                    if text_delta:
                        existing = self.index_to_text.get(idx, "")
                        self.index_to_text[idx] = existing + text_delta
                        outputs.append(
                            _encode_sse_payload(
                                self._build_chunk_payload(index=idx, text_delta=text_delta)
                            )
                        )
                finish_reason = cand.get("finishReason")
                if isinstance(finish_reason, str):
                    outputs.append(
                        _encode_sse_payload(
                            self._build_chunk_payload(
                                index=idx,
                                text_delta="",
                                finish_reason=finish_reason.lower(),
                            )
                        )
                    )
        return outputs

    def finalize(self) -> list[bytes]:
        if self.done:
            return []
        return [b"data: [DONE]\n\n"]


async def _load_metrics_for_candidates(
    redis,
    logical_model_id: str,
    upstreams: list[PhysicalModel],
) -> dict[str, RoutingMetrics]:
    """
    Load RoutingMetrics for each provider used by the candidate upstreams.
    """
    seen_providers: dict[str, RoutingMetrics] = {}
    for up in upstreams:
        if up.provider_id in seen_providers:
            continue
        metrics = await get_routing_metrics(redis, logical_model_id, up.provider_id)
        if metrics is not None:
            seen_providers[up.provider_id] = metrics
    return seen_providers


async def _get_or_fetch_models(
    redis,
    db: Session,
    current_key: AuthenticatedAPIKey,
) -> ModelsResponse:
    """
    Return a model list scoped to the current API key's allowed providers.

    - 若当前 API Key 没有限制，则返回全局缓存的模型列表；
    - 若存在 provider 限制，则只返回这些 provider 下的模型，不使用全局缓存。
    """
    # 无限制的 Key 可以复用全局缓存，避免频繁扫描数据库。
    if not current_key.has_provider_restrictions:
        cached = await get_models_from_cache(redis)
        if cached:
            return ModelsResponse(**cached)

        try:
            stmt = (
                select(ProviderModel.model_id)
                .where(ProviderModel.disabled.is_(False))
                .order_by(ProviderModel.model_id)
            )
            rows = db.execute(stmt).scalars().all()
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception("Failed to load provider models from database")
            rows = []

        models = [ModelInfo(id=str(model_id)) for model_id in rows if model_id]
        models_response = ModelsResponse(data=models)
        await set_models_cache(redis, models_response.model_dump())
        return models_response

    # Key 具有 provider 限制时，只返回允许的 provider 下的模型，不走全局缓存。
    allowed = [pid for pid in current_key.allowed_provider_ids if pid]
    if not allowed:
        # 理论上不应出现（APIKeyProviderRestrictionService 会清空标志位），但这里兜底返回空列表。
        return ModelsResponse(data=[])

    try:
        stmt = (
            select(ProviderModel.model_id)
            .join(Provider, ProviderModel.provider_id == Provider.id)
            .where(Provider.provider_id.in_(allowed))
            .where(ProviderModel.disabled.is_(False))
            .order_by(ProviderModel.model_id)
        )
        rows = db.execute(stmt).scalars().all()
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to load provider models from database for restricted key %s",
            current_key.id,
        )
        rows = []

    models = [ModelInfo(id=str(model_id)) for model_id in rows if model_id]
    return ModelsResponse(data=models)

def _build_ordered_candidates(
    selected: CandidateScore,
    scored: list[CandidateScore],
) -> list[CandidateScore]:
    """
    Build an ordered list of candidates, putting the selected one (which
    may come from a sticky session) first, followed by the remaining
    scored candidates in descending score order.
    """
    ordered: list[CandidateScore] = [selected]
    for cand in scored:
        if (
            cand.upstream.provider_id == selected.upstream.provider_id
            and cand.upstream.model_id == selected.upstream.model_id
        ):
            continue
        ordered.append(cand)
    return ordered


def _is_retryable_upstream_status(
    provider_id: str,
    status_code: int | None,
) -> bool:
    """
    Decide whether an upstream HTTP status code is worth retrying on a
    different provider.

    Behaviour:
    - Transport-level errors (status_code is None) are always retryable.
    - When a ProviderConfig has explicit `retryable_status_codes`, we use
      that list (typically configured per provider, e.g. OpenAI / Gemini /
      Claude).
    - Otherwise we fall back to a generic rule: 5xx and 429 are retryable.
    """
    if status_code is None:
        return True
    cfg = get_provider_config(provider_id)
    if cfg and cfg.retryable_status_codes:
        return status_code in cfg.retryable_status_codes
    if status_code == 429:
        return True
    if 500 <= status_code <= 599:
        return True
    return False


_GEMINI_MODEL_REGEX = re.compile("gemini", re.IGNORECASE)


def _strip_model_group_prefix(model_value: Any) -> str | None:
    """
    Some upstreams or client SDKs use grouped model ids like
    "provider-2/gemini-3-pro-preview". For routing / logical-model
    lookup purposes we only care about the trailing part (the actual
    model id) but we still forward the full id to upstream.
    """
    if not isinstance(model_value, str):
        return None
    if "/" not in model_value:
        return model_value
    # Example: "provider-2/gemini-3-pro-preview" -> "gemini-3-pro-preview"
    return model_value.split("/", 1)[1]


def _build_model_alias_map(
    providers_with_configs: list[tuple[Provider, ProviderConfig]],
) -> dict[str, dict[str, str]]:
    """
    构建 provider 级别的模型别名映射表：
    {
        provider_slug: {
            "alias-model": "real-upstream-model-id",
            ...
        }
    }

    - 仅使用 ProviderModel.alias 非空的行；
    - 若同一 Provider 下出现重复别名，优先保留第一条并记录告警日志。
    """
    mapping: dict[str, dict[str, str]] = {}
    for provider_row, cfg in providers_with_configs:
        alias_map: dict[str, str] = {}
        for model in getattr(provider_row, "models", []) or []:
            if bool(getattr(model, "disabled", False)):
                continue
            alias_value = getattr(model, "alias", None)
            if not isinstance(alias_value, str):
                continue

            alias_str = alias_value.strip()
            if not alias_str:
                continue

            if alias_str in alias_map:
                # 尽量避免 hard fail，仅记录日志并保留第一条。
                logger.warning(
                    "Duplicate model alias '%s' for provider %s (models %s vs %s); "
                    "keeping the first mapping.",
                    alias_str,
                    provider_row.provider_id,
                    alias_map[alias_str],
                    model.model_id,
                )
                continue

            alias_map[alias_str] = model.model_id

        if alias_map:
            mapping[cfg.id] = alias_map
    return mapping


def _build_model_capabilities_override_map(
    providers_with_configs: list[tuple[Provider, ProviderConfig]],
) -> dict[str, dict[str, set[ModelCapability]]]:
    """
    读取 provider_models.metadata_json 中 `_gateway.capabilities_override` 并构建覆盖表：
    {
        provider_slug: {
            "upstream-model-id": {ModelCapability.CHAT, ...},
            ...
        }
    }
    """
    mapping: dict[str, dict[str, set[ModelCapability]]] = {}
    for provider_row, cfg in providers_with_configs:
        per: dict[str, set[ModelCapability]] = {}
        for model in getattr(provider_row, "models", []) or []:
            if bool(getattr(model, "disabled", False)):
                continue
            meta = getattr(model, "metadata_json", None)
            if not isinstance(meta, dict):
                continue
            gateway = meta.get("_gateway")
            if not isinstance(gateway, dict):
                continue
            override = gateway.get("capabilities_override")
            if not isinstance(override, list) or not override:
                continue
            caps: set[ModelCapability] = set()
            for item in override:
                try:
                    caps.add(ModelCapability(str(item)))
                except ValueError:
                    continue
            if caps:
                per[str(model.model_id)] = caps
        if per:
            mapping[cfg.id] = per
    return mapping


async def _build_dynamic_logical_model_for_group(
    *,
    client: httpx.AsyncClient,
    redis,
    requested_model: Any,
    lookup_model_id: str | None,
    api_style: str,
    db: Session | None = None,
    allowed_provider_ids: set[str] | None = None,
    user_id: UUID | None = None,
    is_superuser: bool = False,
) -> LogicalModel | None:
    """
    Build a transient LogicalModel for cases where no static logical
    model is configured for the requested id.

    Behaviour:
    - Discover all providers whose /models list includes either the
      exact requested model id or a model whose stripped suffix matches
      the requested id (to account for grouped ids like "provider-2/xxx").
    - When multiple providers advertise the same underlying model, we
      treat them as a single logical model group and let the scheduler
      perform cross-provider load-balancing with session stickiness.
    - When no provider claims the model, we return None so that the
      caller can reject the request at the gateway.
    """
    if not isinstance(lookup_model_id, str):
        return None

    # When a DB session is available, we prefer to load providers together
    # with their ORM objects so that we can honour per-model alias mappings
    # stored in provider_models.alias.
    alias_map: dict[str, dict[str, str]] = {}
    capabilities_override_map: dict[str, dict[str, set[ModelCapability]]] = {}
    if db is not None:
        providers_with_configs = load_providers_with_configs(
            session=db,
            user_id=user_id,
            is_superuser=is_superuser,
        )
        providers = [cfg for (_provider, cfg) in providers_with_configs]
        alias_map = _build_model_alias_map(providers_with_configs)
        capabilities_override_map = _build_model_capabilities_override_map(
            providers_with_configs
        )
    else:
        providers = load_provider_configs(
            user_id=user_id,
            is_superuser=is_superuser,
        )

    if not providers:
        return None

    target_model_str = str(requested_model) if isinstance(requested_model, str) else None
    target_base = _strip_model_group_prefix(target_model_str) if target_model_str else None

    # Discover all providers that advertise this model.
    candidate_upstreams: list[PhysicalModel] = []
    merged_capabilities: set[ModelCapability] = set()
    now = time.time()

    for cfg in providers:
        if allowed_provider_ids is not None and cfg.id not in allowed_provider_ids:
            continue
        provider_alias_map = alias_map.get(cfg.id) or {}
        try:
            items = await ensure_provider_models_cached(client, redis, cfg)
        except httpx.HTTPError as exc:
            # Skip providers whose /models endpoint is currently failing
            # for this request; other providers may still be usable.
            logger.warning(
                "Failed to refresh models for provider %s while building "
                "dynamic logical model for %s: %s",
                cfg.id,
                lookup_model_id,
                exc,
            )
            continue

        matched_full_id: str | None = None
        matched_caps: set[ModelCapability] | None = None

        caps_by_model_id: dict[str, set[ModelCapability]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            mid_val = item.get("id") or item.get("model_id")
            if not isinstance(mid_val, str) or not mid_val:
                continue
            raw_caps = item.get("capabilities") or []
            caps: set[ModelCapability] = set()
            if isinstance(raw_caps, list):
                for c in raw_caps:
                    try:
                        caps.add(ModelCapability(str(c)))
                    except ValueError:
                        continue
            elif isinstance(raw_caps, str):
                try:
                    caps.add(ModelCapability(raw_caps))
                except ValueError:
                    pass
            if caps:
                caps_by_model_id[mid_val] = caps

        for item in items:
            mid: str | None = None
            if isinstance(item, dict):
                mid_val = item.get("id") or item.get("model_id")
                if isinstance(mid_val, str):
                    mid = mid_val
            elif isinstance(item, str):
                mid = item
            if mid is None:
                continue

            base_id = _strip_model_group_prefix(mid) or mid

            if not target_model_str:
                continue

            if (
                target_model_str == mid
                or (target_base is not None and target_base == mid)
                or (target_base is not None and target_base == base_id)
            ):
                matched_full_id = mid
                override_caps = (
                    capabilities_override_map.get(cfg.id, {}).get(mid)
                    or capabilities_override_map.get(cfg.id, {}).get(base_id)
                )
                matched_caps = override_caps or caps_by_model_id.get(mid)
                break

        # Fallback: try to resolve via per-provider alias mapping when the
        # requested model id itself does not appear in the upstream catalogue.
        if matched_full_id is None and provider_alias_map and target_model_str:
            alias_target: str | None = None
            if target_model_str in provider_alias_map:
                alias_target = provider_alias_map[target_model_str]
            elif target_base is not None and target_base in provider_alias_map:
                alias_target = provider_alias_map[target_base]

            if alias_target:
                # Only honour aliases that point to a model actually advertised
                # by this provider, to avoid routing to non-existent ids.
                advertised_ids = set()
                for item in items:
                    if isinstance(item, dict):
                        mid_val = item.get("id") or item.get("model_id")
                        if isinstance(mid_val, str):
                            advertised_ids.add(mid_val)
                    elif isinstance(item, str):
                        advertised_ids.add(item)

                if alias_target in advertised_ids:
                    matched_full_id = alias_target
                    override_caps = capabilities_override_map.get(cfg.id, {}).get(alias_target)
                    matched_caps = override_caps or caps_by_model_id.get(alias_target)
                else:
                    logger.warning(
                        "Alias '%s' for provider %s maps to '%s' which is not present "
                        "in /models cache; alias ignored.",
                        target_model_str,
                        cfg.id,
                        alias_target,
                    )

        if matched_full_id is None:
            continue

        selection = _select_provider_endpoint(cfg, api_style)
        if selection is None:
            continue
        endpoint = selection.url
        upstream_style = selection.api_style
        base_weight = getattr(cfg, "weight", 1.0) or 1.0

        candidate_upstreams.append(
            PhysicalModel(
                provider_id=cfg.id,
                model_id=matched_full_id,
                endpoint=endpoint,
                base_weight=base_weight,
                region=getattr(cfg, "region", None),
                max_qps=getattr(cfg, "max_qps", None),
                meta_hash=None,
                updated_at=now,
                api_style=upstream_style,
            )
        )
        if matched_caps:
            merged_capabilities.update(matched_caps)
    if not candidate_upstreams:
        return None

    if not merged_capabilities:
        merged_capabilities = {ModelCapability.CHAT}

    return LogicalModel(
        logical_id=lookup_model_id,
        display_name=lookup_model_id,
        description=f"Dynamic logical model for '{lookup_model_id}'",
        capabilities=sorted(merged_capabilities, key=lambda c: c.value),
        upstreams=candidate_upstreams,
        enabled=True,
        updated_at=now,
    )


def _normalize_gemini_input_to_messages(input_value: Any) -> list[dict[str, str]]:
    """
    Convert a Gemini-style `input` list into OpenAI-style `messages`.
    This is a best-effort adapter so that clients that speak Gemini
    can still go through the OpenAI-compatible /v1/chat/completions
    upstream endpoint.
    """
    if not isinstance(input_value, list):
        return []

    messages: list[dict[str, str]] = []

    for item in input_value:
        if not isinstance(item, dict):
            continue

        role = item.get("role") or "user"
        content = item.get("content", "")

        # Gemini-style content might be:
        # - a plain string
        # - a list of segments like {"type": "input_text", "text": "..."}
        text: str
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif part.get("type") == "input_text" and isinstance(
                    part.get("text"), str
                ):
                    parts.append(part["text"])
            text = "".join(parts)
        else:
            text = str(content)

        messages.append({"role": role, "content": text})

    return messages


def _normalize_payload_by_model(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Inspect payload.model + structure, and normalize provider-specific
    formats (e.g. Gemini) into the OpenAI-style shape expected by the
    upstream chat APIs.
    """
    model = payload.get("model")
    model_str = str(model or "")

    # Gemini-style: caller sends `input=[{role, content: [...]}, ...]`
    # instead of OpenAI `messages=[{role, content: "..."}, ...]`.
    if (
        "input" in payload
        and "messages" not in payload
        and _GEMINI_MODEL_REGEX.search(model_str)
    ):
        logger.info(
            "Normalizing Gemini-style payload for model %s into OpenAI messages",
            model_str,
        )
        messages = _normalize_gemini_input_to_messages(payload.get("input"))
        if messages:
            new_payload = dict(payload)
            new_payload["messages"] = messages
            new_payload.pop("input", None)
            return new_payload

    # Default: return as-is
    return payload


def _flatten_responses_content(content: Any) -> str | None:
    """
    Best-effort extraction of plain text from OpenAI Responses-style content
    blocks. These blocks may be strings or a list of dict segments
    containing text fields.
    """
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif isinstance(part.get("content"), str):
                    parts.append(part["content"])
        if parts:
            return "".join(parts)
        return None
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
    return str(content)


def _convert_responses_messages(
    input_value: Any, instructions: str | None
) -> list[dict[str, str]]:
    """
    Convert Responses API `input` + optional `instructions` into
    OpenAI-style chat messages.
    """
    messages: list[dict[str, str]] = []

    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions.strip()})

    if isinstance(input_value, list):
        for item in input_value:
            if not isinstance(item, dict):
                continue
            role = item.get("role") or "user"
            text = _flatten_responses_content(item.get("content"))
            if text:
                messages.append({"role": role, "content": text})
    elif isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
    elif input_value is not None:
        messages.append({"role": "user", "content": str(input_value)})

    return messages


def _adapt_responses_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Adapt a Responses API payload into the chat-completions-friendly shape.
    This primarily maps `instructions` + `input` into `messages`.
    """
    payload = dict(raw_payload)

    if "messages" in payload:
        return payload

    instructions = payload.pop("instructions", None)
    input_value = payload.pop("input", None)
    messages = _convert_responses_messages(input_value, instructions)

    if messages:
        payload["messages"] = messages
    else:
        # Put the original fields back if we failed to convert, so the caller
        # still receives a meaningful error downstream.
        if instructions is not None:
            payload["instructions"] = instructions
        if input_value is not None:
            payload["input"] = input_value

    return payload


def _ensure_response_id(response_id: str | None) -> str:
    return response_id or f"resp-{int(time.time() * 1000)}"


def _build_output_blocks_from_text_map(
    response_id: str,
    index_to_text: dict[int, str],
) -> list[dict[str, Any]]:
    if not index_to_text:
        return [
            {
                "id": f"{response_id}-msg-0",
                "type": "message",
                "role": "assistant",
                "content": [],
            }
        ]

    blocks: list[dict[str, Any]] = []
    for idx in sorted(index_to_text):
        text = index_to_text[idx]
        blocks.append(
            {
                "id": f"{response_id}-msg-{idx}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            }
        )
    return blocks


def _text_map_from_choices(choices: Any) -> dict[int, str]:
    text_map: dict[int, str] = {}
    if not isinstance(choices, list):
        return text_map
    for idx, choice in enumerate(choices):
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        content = message.get("content")
        text = _flatten_responses_content(content) or ""
        text_map[idx] = text
    return text_map


def _chat_to_responses_payload(chat_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a chat-completions JSON payload into Responses API shape.
    """
    response_id = _ensure_response_id(chat_payload.get("id"))
    created = chat_payload.get("created") or int(time.time())
    text_map = _text_map_from_choices(chat_payload.get("choices"))
    output_blocks = _build_output_blocks_from_text_map(response_id, text_map)
    output_text = "\n".join(text_map[idx] for idx in sorted(text_map) if text_map[idx])
    payload = {
        "id": response_id,
        "object": "response",
        "created": created,
        "model": chat_payload.get("model"),
        "usage": chat_payload.get("usage"),
        "status": "completed",
        "output": output_blocks,
        "output_text": output_text,
        "metadata": chat_payload.get("metadata") or {},
    }
    return payload


def _encode_sse_payload(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _build_completed_event_payload(
    response_id: str | None,
    model: str | None,
    created: int | None,
    index_to_text: dict[int, str],
    usage: dict[str, Any] | None,
) -> dict[str, Any]:
    rid = _ensure_response_id(response_id)
    created_ts = created or int(time.time())
    outputs = _build_output_blocks_from_text_map(rid, index_to_text)
    aggregated_text = "\n".join(
        index_to_text[idx] for idx in sorted(index_to_text) if index_to_text[idx]
    )
    response_body = {
        "id": rid,
        "object": "response",
        "created": created_ts,
        "model": model,
        "status": "completed",
        "output": outputs,
        "output_text": aggregated_text,
        "usage": usage,
        "metadata": {},
    }
    return {
        "id": rid,
        "type": "response.completed",
        "response": response_body,
    }


def _build_created_event_payload(
    response_id: str | None,
    model: str | None,
    created: int | None,
) -> dict[str, Any]:
    rid = _ensure_response_id(response_id)
    created_ts = created or int(time.time())
    response_body = {
        "id": rid,
        "object": "response",
        "created": created_ts,
        "model": model,
        "status": "in_progress",
        "output": [],
        "metadata": {},
    }
    return {
        "id": rid,
        "type": "response.created",
        "response": response_body,
    }


def _build_output_done_event_payload(
    response_id: str | None,
    output_index: int,
) -> dict[str, Any]:
    rid = _ensure_response_id(response_id)
    return {
        "id": rid,
        "type": "response.output_text.done",
        "response_id": rid,
        "output_index": output_index,
    }


def _wrap_chat_stream_response(chat_response: StreamingResponse) -> StreamingResponse:
    """
    Consume the original chat completion SSE stream and emit responses-style events.
    """

    async def _iterator() -> AsyncIterator[bytes]:
        buffer = ""
        index_to_text: dict[int, str] = {}
        response_id: str | None = None
        model: str | None = None
        created: int | None = None
        usage: dict[str, Any] | None = None
        created_emitted = False
        completed_emitted = False
        done_indices: set[int] = set()

        def _get_or_create_response_id() -> str:
            nonlocal response_id
            rid = _ensure_response_id(response_id)
            response_id = rid
            return rid

        def _maybe_emit_created_event() -> bytes | None:
            nonlocal created_emitted
            if created_emitted:
                return None
            rid = _get_or_create_response_id()
            created_payload = _build_created_event_payload(
                rid,
                model,
                created,
            )
            created_emitted = True
            return _encode_sse_payload(created_payload)

        def _emit_output_done(idx: int) -> bytes | None:
            if idx in done_indices:
                return None
            rid = _get_or_create_response_id()
            done_indices.add(idx)
            return _encode_sse_payload(
                _build_output_done_event_payload(rid, idx)
            )

        def _flush_all_output_done_events() -> list[bytes]:
            payloads: list[bytes] = []
            for idx in sorted(index_to_text):
                payload = _emit_output_done(idx)
                if payload:
                    payloads.append(payload)
            return payloads

        async for chunk in chat_response.body_iterator:
            try:
                decoded = chunk.decode("utf-8")
            except UnicodeDecodeError:
                continue
            buffer += decoded

            while "\n\n" in buffer:
                raw_event, buffer = buffer.split("\n\n", 1)
                raw_event = raw_event.strip()
                if not raw_event.startswith("data:"):
                    continue
                payload_str = raw_event[len("data:") :].strip()
                if not payload_str:
                    continue

                if payload_str == "[DONE]":
                    if not created_emitted:
                        created_payload = _maybe_emit_created_event()
                        if created_payload:
                            yield created_payload
                    for payload in _flush_all_output_done_events():
                        yield payload
                    if not completed_emitted:
                        completed = _build_completed_event_payload(
                            response_id,
                            model,
                            created,
                            index_to_text,
                            usage,
                        )
                        yield _encode_sse_payload(completed)
                        completed_emitted = True
                    yield b"data: [DONE]\n\n"
                    return

                try:
                    data = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue

                if data.get("object") != "chat.completion.chunk":
                    continue

                if isinstance(data.get("id"), str):
                    response_id = response_id or data["id"]
                model = model or data.get("model")
                created = created or data.get("created")
                if data.get("usage"):
                    usage = data["usage"]

                for choice in data.get("choices", []):
                    if not isinstance(choice, dict):
                        continue
                    idx = choice.get("index", 0)
                    delta = choice.get("delta") or {}
                    delta_content = delta.get("content")
                    text_delta = _flatten_responses_content(delta_content)
                    if text_delta:
                        existing = index_to_text.get(idx, "")
                        index_to_text[idx] = existing + text_delta
                        created_payload = _maybe_emit_created_event()
                        if created_payload:
                            yield created_payload
                        rid = _get_or_create_response_id()
                        yield _encode_sse_payload(
                            {
                                "id": rid,
                                "type": "response.output_text.delta",
                                "response_id": rid,
                                "output_index": idx,
                                "delta": text_delta,
                            }
                        )

                    if choice.get("finish_reason"):
                        done_payload = _emit_output_done(idx)
                        if done_payload:
                            yield done_payload
                    if choice.get("finish_reason") and not completed_emitted:
                        if not created_emitted:
                            created_payload = _maybe_emit_created_event()
                            if created_payload:
                                yield created_payload
                        completed = _build_completed_event_payload(
                            response_id,
                            model,
                            created,
                            index_to_text,
                            usage,
                        )
                        yield _encode_sse_payload(completed)
                        completed_emitted = True

        # Safety net: emit completion even if upstream stream ended abruptly.
        if not completed_emitted:
            if not created_emitted:
                created_payload = _maybe_emit_created_event()
                if created_payload:
                    yield created_payload
            for payload in _flush_all_output_done_events():
                yield payload
            completed = _build_completed_event_payload(
                response_id,
                model,
                created,
                index_to_text,
                usage,
            )
            yield _encode_sse_payload(completed)
            yield b"data: [DONE]\n\n"

    headers = dict(chat_response.headers)
    headers.pop("content-length", None)
    return StreamingResponse(
        _iterator(),
        media_type="text/event-stream",
        headers=headers,
        status_code=chat_response.status_code,
        background=chat_response.background,
    )
