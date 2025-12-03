import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas import (
    LogicalModel,
    ModelCapability,
    PhysicalModel,
    ProviderConfig,
    RoutingMetrics,
    SchedulingStrategy,
    Session,
)
from app.provider.config import get_provider_config, load_provider_configs
from app.provider.discovery import ensure_provider_models_cached
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
from app.storage.redis_service import get_logical_model, get_routing_metrics

from .auth import AuthenticatedAPIKey, require_api_key
from .context_store import save_context
from .deps import get_db, get_http_client, get_redis
from .db import SessionLocal
from .errors import forbidden
from .logging_config import logger
from .api.auth_routes import router as auth_router
from .api.logical_model_routes import router as logical_model_router
from .api.provider_routes import router as provider_router
from .api.routing_routes import router as routing_router
from .api.session_routes import router as session_router
from .api.system_routes import router as system_router
from .api.v1.api_key_routes import router as api_key_router
from .api.v1.provider_key_routes import router as provider_key_router
from .api.v1.user_routes import router as user_router
from .model_cache import get_models_from_cache, set_models_cache
from .models import ProviderModel
from .services.bootstrap_admin import ensure_initial_admin
from .settings import settings
from .upstream import UpstreamStreamError, detect_request_format, stream_upstream


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


async def _build_provider_headers(
    provider_cfg: ProviderConfig, redis
) -> tuple[dict[str, str], SelectedProviderKey]:
    """
    Build headers for calling a concrete provider upstream.

    This reuses the browser-mimic settings (User-Agent / Origin / Referer)
    but replaces the Authorization header with a selected provider-specific API key.
    """
    key_selection = await acquire_provider_key(provider_cfg, redis)
    headers: dict[str, str] = {
        "Authorization": f"Bearer {key_selection.key}",
        "Accept": "application/json",
    }

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
class ClaudeFallbackOutcome:
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
        self.stop_reason: str | None = None
        self.usage: dict[str, Any] | None = None
        self.aggregate_text: str = ""

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
                finish_reason = choice.get("finish_reason")
                if isinstance(finish_reason, str):
                    self.stop_reason = _map_openai_finish_reason(finish_reason)
            usage = data.get("usage")
            if isinstance(usage, dict):
                self.usage = _openai_usage_to_claude_usage(usage)
        return outputs

    def finalize(self) -> list[bytes]:
        outputs: list[bytes] = []
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
                    "usage": self.usage,
                },
            )
        )
        outputs.append(
            self._encode_event(
                "message_stop",
                {
                    "type": "message_stop",
                    "message": {
                        "id": self.message_id,
                        "type": "message",
                        "role": "assistant",
                        "model": self.model,
                        "content": [
                            {"type": "text", "text": self.aggregate_text},
                        ],
                    },
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
    payload: dict[str, Any],
    fallback_url: str | None,
    redis,
    x_session_id: str | None,
    bind_session,
) -> ClaudeFallbackOutcome:
    if not fallback_url:
        return ClaudeFallbackOutcome(
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
        response = await client.post(fallback_url, headers=headers, json=fallback_payload)
    except httpx.HTTPError as exc:
        return ClaudeFallbackOutcome(
            response=None, retryable=True, status_code=None, error_text=str(exc)
        )

    text = response.text
    status_code = response.status_code

    if status_code >= 400:
        return ClaudeFallbackOutcome(
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
        return ClaudeFallbackOutcome(
            response=JSONResponse(content={"raw": text}, status_code=status_code)
        )

    claude_payload = _openai_chat_to_claude_response(
        payload_json, request_model=payload.get("model") or model_id
    )
    return ClaudeFallbackOutcome(
        response=JSONResponse(content=claude_payload, status_code=status_code)
    )


async def _claude_streaming_fallback_iterator(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    provider_id: str,
    model_id: str,
    fallback_url: str | None,
    payload: dict[str, Any],
    redis,
    session_id: str | None,
    bind_session_cb,
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
        async for chunk in stream_upstream(
            client=client,
            method="POST",
            url=fallback_url,
            headers=headers,
            json_body=fallback_payload,
            redis=redis,
            session_id=session_id,
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
) -> ModelsResponse:
    """
    Return cached models when available, otherwise fall back to the DB snapshot.
    """
    cached = await get_models_from_cache(redis)
    if cached:
        return ModelsResponse(**cached)

    try:
        stmt = select(ProviderModel.model_id).order_by(ProviderModel.model_id)
        rows = db.execute(stmt).scalars().all()
    except Exception:
        logger.exception("Failed to load provider models from database")
        rows = []

    models = [ModelInfo(id=str(model_id)) for model_id in rows if model_id]

    models_response = ModelsResponse(data=models)
    await set_models_cache(redis, models_response.model_dump())
    return models_response

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


async def _build_dynamic_logical_model_for_group(
    *,
    client: httpx.AsyncClient,
    redis,
    requested_model: Any,
    lookup_model_id: str | None,
    api_style: str,
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

    providers = load_provider_configs()
    if not providers:
        return None

    target_model_str = str(requested_model) if isinstance(requested_model, str) else None
    target_base = _strip_model_group_prefix(target_model_str) if target_model_str else None

    # Discover all providers that advertise this model.
    candidate_upstreams: list[PhysicalModel] = []
    now = time.time()

    for cfg in providers:
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
                break

        if matched_full_id is None:
            continue

        is_sdk_transport = getattr(cfg, "transport", "http") == "sdk"
        if is_sdk_transport:
            endpoint = str(cfg.base_url).rstrip("/")
        else:
            if api_style == "claude":
                relative_path = getattr(cfg, "messages_path", None) or "/v1/message"
            elif api_style == "responses":
                relative_path = "/v1/responses"
            else:
                relative_path = "/v1/chat/completions"

            endpoint = f"{str(cfg.base_url).rstrip('/')}{relative_path}"
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
            )
        )

    if not candidate_upstreams:
        return None

    return LogicalModel(
        logical_id=lookup_model_id,
        display_name=lookup_model_id,
        description=f"Dynamic logical model for '{lookup_model_id}'",
        capabilities=[ModelCapability.CHAT],
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


def create_app() -> FastAPI:
    app = FastAPI(title="AI Gateway", version="0.1.0")
    # Authentication API for user login and JWT tokens.
    app.include_router(auth_router)
    # System management API.
    app.include_router(system_router)
    # Provider-management API (multi-provider routing feature).
    app.include_router(provider_router)
    # Logical model mapping API (User Story 2).
    app.include_router(logical_model_router)
    # Routing decision and session APIs (User Story 3).
    app.include_router(routing_router)
    app.include_router(session_router)
    
    # User and API key management - using JWT authentication
    app.include_router(user_router)
    app.include_router(api_key_router)
    app.include_router(provider_key_router)

    @app.on_event("startup")
    async def _ensure_admin_account() -> None:
        session = SessionLocal()
        try:
            ensure_initial_admin(session)
        finally:
            session.close()

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Basic request/response logging middleware.
        Also logs all request headers so we can inspect how different
        clients are passing session-related information.
        """
        client_host = request.client.host if request.client else "-"
        # Copy headers into a plain dict; redact Authorization by default.
        headers_for_log = {}
        for k, v in request.headers.items():
            if k.lower() == "authorization":
                headers_for_log[k] = "***REDACTED***"
            else:
                headers_for_log[k] = v

        logger.info(
            "HTTP %s %s from %s, headers=%s",
            request.method,
            request.url.path,
            client_host,
            headers_for_log,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error while processing %s %s",
                request.method,
                request.url.path,
            )
            raise
        logger.info(
            "HTTP %s %s -> %s", request.method, request.url.path, response.status_code
        )
        return response

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get(
        "/models",
        response_model=ModelsResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def list_models(
        redis=Depends(get_redis),
        db: Session = Depends(get_db),
    ) -> ModelsResponse:
        models_response = await _get_or_fetch_models(redis, db)
        return models_response

    @app.get(
        "/v1/models",
        response_model=ModelsResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def list_models_v1(
        redis=Depends(get_redis),
        db: Session = Depends(get_db),
    ) -> ModelsResponse:
        """
        向后兼容的别名：某些 SDK 默认请求 /v1/models。
        """
        return await list_models(redis=redis, db=db)

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        client: httpx.AsyncClient = Depends(get_http_client),
        redis=Depends(get_redis),
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
            session_obj: Session | None = None
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
                            sdk_payload = await driver.generate_content(
                                api_key=key_selection.key,
                                model_id=model_id,
                                payload=payload,
                                base_url=normalize_base_url(provider_cfg.base_url),
                            )
                        except driver.error_types as exc:
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
                                payload=payload,
                                fallback_url=fallback_url or base_endpoint,
                                redis=redis,
                                x_session_id=x_session_id,
                                bind_session=_bind_session_for_upstream,
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

                    try:
                        # Use a provider-specific model id when forwarding
                        # upstream so that grouped ids like "provider-2/xxx"
                        # are translated correctly for each vendor.
                        upstream_payload = dict(payload)
                        upstream_payload["model"] = model_id

                        r = await client.post(url, headers=headers, json=upstream_payload)
                    except httpx.HTTPError as exc:
                        if key_selection:
                            record_key_failure(
                                key_selection, retryable=True, status_code=None, redis=redis
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
                            payload=payload,
                            fallback_url=fallback_url or base_endpoint,
                            redis=redis,
                            x_session_id=x_session_id,
                            bind_session=_bind_session_for_upstream,
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
                        return JSONResponse(
                            content=converted_payload,
                            status_code=status_code,
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
                            async for chunk_dict in driver.stream_content(
                                api_key=key_selection.key,
                                model_id=model_id,
                                payload=payload,
                                base_url=normalize_base_url(provider_cfg.base_url),
                            ):
                                sse_chunk = _encode_sse_payload(chunk_dict)
                                if adapter:
                                    converted_chunks = adapter.process_chunk(sse_chunk)
                                    for item in converted_chunks:
                                        if not first_chunk_seen:
                                            await _bind_session_for_upstream(
                                                provider_id, model_id
                                            )
                                            first_chunk_seen = True
                                        yield item
                                else:
                                    if not first_chunk_seen:
                                        await _bind_session_for_upstream(
                                            provider_id, model_id
                                        )
                                        first_chunk_seen = True
                                    yield sse_chunk
                            if adapter:
                                for tail in adapter.finalize():
                                    yield tail
                            else:
                                yield b"data: [DONE]\n\n"
                            record_key_success(key_selection, redis=redis)
                            _mark_provider_success(provider_id)
                            return
                        except driver.error_types as exc:
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
                                fallback_url=fallback_url or base_endpoint,
                                payload=payload,
                                redis=redis,
                                session_id=x_session_id,
                                bind_session_cb=_bind_session_for_upstream,
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

                        async for chunk in stream_upstream(
                            client=client,
                            method="POST",
                            url=url,
                            headers=headers,
                            json_body=upstream_payload,
                            redis=redis,
                            session_id=x_session_id,
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
                                    fallback_url=fallback_url or base_endpoint,
                                    payload=payload,
                                    redis=redis,
                                    session_id=x_session_id,
                                    bind_session_cb=_bind_session_for_upstream,
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

            return StreamingResponse(
                routed_iterator(), media_type="text/event-stream"
            )

    @app.post("/v1/responses")
    async def responses_endpoint(
        request: Request,
        client: httpx.AsyncClient = Depends(get_http_client),
        redis=Depends(get_redis),
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

    @app.post("/v1/messages")
    async def claude_messages_endpoint(
        request: Request,
        client: httpx.AsyncClient = Depends(get_http_client),
        redis=Depends(get_redis),
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

    @app.get(
        "/context/{session_id}",
        dependencies=[Depends(require_api_key)],
    )
    async def get_context(
        session_id: str,
        redis=Depends(get_redis),
    ):
        """
        Simple endpoint to inspect stored conversation context for a session.
        """
        key = f"session:{session_id}:history"
        items = await redis.lrange(key, 0, -1)
        return {"session_id": session_id, "history": items}

    return app
