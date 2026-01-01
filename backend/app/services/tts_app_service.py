from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import struct
import time
import unicodedata
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.auth import AuthenticatedAPIKey
from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.models import Provider, ProviderModel
from app.provider import config as provider_config
from app.provider.key_pool import (
    NoAvailableProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)
from app.schemas.audio import SpeechRequest
from app.schemas.model import ModelCapability
from app.services.credit_service import InsufficientCreditsError, ensure_account_usable
from app.services.metrics_service import record_provider_call_metric
from app.services.user_provider_service import get_accessible_provider_ids

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_CHARS_RE = re.compile(r"[*_`#~]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

_TTS_USER_LIMIT_PER_MINUTE = 20
_TTS_GLOBAL_LIMIT_PER_MINUTE = 1000

_CACHE_TTL_SECONDS = 7 * 24 * 3600
_LOCK_TTL_SECONDS = 60
_CACHE_CHUNK_SIZE = 64 * 1024
_MAX_CACHE_BYTES = 4 * 1024 * 1024

_CACHEABLE_FORMATS: set[str] = {"mp3", "aac", "opus", "wav", "ogg", "flac", "aiff", "pcm"}

_OPENAI_AUDIO_PATH_FALLBACK = "/v1/audio/speech"

_GEMINI_BASE_URL_HOST = "generativelanguage.googleapis.com"

_GEMINI_VOICE_MAPPING: dict[str, str] = {
    "alloy": "Charon",
    "echo": "Enceladus",
    "fable": "Fenrir",
    "onyx": "Orus",
    "nova": "Puck",
    "shimmer": "Zephyr",
}

_OPENAI_OFFICIAL_HOSTS: set[str] = {"api.openai.com"}


def _is_google_native_provider_base_url(base_url: str) -> bool:
    raw = str(base_url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlsplit(raw)
    except Exception:
        return False
    return str(parsed.netloc or "").lower() == _GEMINI_BASE_URL_HOST


def _is_openai_official_provider_base_url(base_url: str) -> bool:
    """
    OpenAI 官方 API 对未知字段通常会严格校验；为避免“可选扩展字段”导致请求失败，
    对官方域名默认不透传扩展字段。
    """
    raw = str(base_url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlsplit(raw)
    except Exception:
        return False
    host = str(parsed.netloc or "").lower()
    # netloc may include port
    host = host.split(":", 1)[0]
    return host in _OPENAI_OFFICIAL_HOSTS


def _derive_openai_audio_speech_path(provider_cfg) -> str:
    """
    尽量从 provider 的已知 path 推导 /audio/speech，兼容 base_url 是否自带 /v1 两种配置。
    """
    raw = str(getattr(provider_cfg, "chat_completions_path", None) or "").strip()
    lowered = raw.lower()
    if raw and "chat/completions" in lowered:
        prefix = raw[: lowered.rfind("chat/completions")]
        return f"{prefix}audio/speech".replace("//", "/")

    raw = str(getattr(provider_cfg, "images_generations_path", None) or "").strip()
    lowered = raw.lower()
    if raw and "images/generations" in lowered:
        prefix = raw[: lowered.rfind("images/generations")]
        return f"{prefix}audio/speech".replace("//", "/")

    return _OPENAI_AUDIO_PATH_FALLBACK


def _content_type_for_format(response_format: str) -> str:
    fmt = str(response_format or "").strip().lower()
    if fmt == "mp3":
        return "audio/mpeg"
    if fmt == "opus":
        return "audio/opus"
    if fmt == "aac":
        return "audio/aac"
    if fmt == "wav":
        return "audio/wav"
    if fmt == "pcm":
        return "audio/pcm"
    if fmt == "ogg":
        return "audio/ogg"
    if fmt == "flac":
        return "audio/flac"
    if fmt == "aiff":
        return "audio/aiff"
    return "application/octet-stream"


def _extract_text_from_message_content(content: Any) -> str | None:
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip() or None
    return None


def _parse_mime_type(value: str) -> tuple[str, dict[str, str]]:
    raw = str(value or "").strip()
    if not raw:
        return "", {}
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    primary = parts[0].lower()
    params: dict[str, str] = {}
    for p in parts[1:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        params[k.strip().lower()] = v.strip()
    return primary, params


def _normalize_audio_format_from_mime(primary_mime: str) -> str | None:
    """
    将上游返回的 mimeType 归一化为网关 response_format。
    注意：这里不做转码，仅用于“是否与请求的 response_format 匹配”的判断。
    """
    mime = str(primary_mime or "").strip().lower()
    if not mime:
        return None
    if mime in ("audio/mpeg", "audio/mp3"):
        return "mp3"
    if mime == "audio/aac":
        return "aac"
    if mime == "audio/opus":
        return "opus"
    if mime == "audio/wav":
        return "wav"
    if mime == "audio/ogg":
        return "ogg"
    if mime == "audio/flac":
        return "flac"
    if mime == "audio/aiff":
        return "aiff"
    if mime in ("audio/l16", "audio/pcm"):
        return "pcm"
    return None


def _wrap_pcm_as_wav(
    pcm: bytes, *, sample_rate: int = 24000, channels: int = 1, sample_width_bytes: int = 2
) -> bytes:
    """
    将 16-bit PCM（小端）封装为 WAV，不做重采样/转码。
    参考 Gemini 官方示例：默认 24kHz / mono / 16-bit。
    """
    sample_rate = int(sample_rate)
    channels = int(channels)
    sample_width_bytes = int(sample_width_bytes)
    if sample_rate <= 0 or channels <= 0 or sample_width_bytes <= 0:
        raise ValueError("invalid wav params")

    subchunk2_size = len(pcm)
    byte_rate = sample_rate * channels * sample_width_bytes
    block_align = channels * sample_width_bytes
    bits_per_sample = sample_width_bytes * 8
    chunk_size = 36 + subchunk2_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        subchunk2_size,
    )
    return header + pcm


def _model_requires_reference_audio(metadata: Any) -> bool:
    """
    Best-effort flag reader for provider_models.metadata_json.

    Reserved key space:
    - metadata_json["_gateway"]["tts"]["requires_reference_audio"] == true/false
    """
    if not isinstance(metadata, dict):
        return False
    gateway = metadata.get("_gateway")
    if not isinstance(gateway, dict):
        return False
    tts = gateway.get("tts")
    if not isinstance(tts, dict):
        return False
    value = tts.get("requires_reference_audio")
    return bool(value) if isinstance(value, bool) else False


def _build_openai_compatible_tts_payload(
    *,
    provider_model_id: str,
    processed_text: str,
    request: SpeechRequest,
    allow_extensions: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": provider_model_id,
        "input": processed_text,
        "voice": request.voice,
        "response_format": request.response_format,
        "speed": float(request.speed),
    }
    if request.instructions:
        payload["instructions"] = str(request.instructions)
    if allow_extensions:
        if request.locale:
            payload["locale"] = str(request.locale)
        if request.pitch is not None:
            payload["pitch"] = float(request.pitch)
        if request.volume is not None:
            payload["volume"] = float(request.volume)
        if request.reference_audio_url is not None:
            payload["reference_audio_url"] = str(request.reference_audio_url)
    return payload


def _build_gemini_tts_payload(*, request: SpeechRequest, processed_text: str) -> dict[str, Any]:
    voice_name = _GEMINI_VOICE_MAPPING.get(str(request.voice), "Kore")
    return {
        "contents": [{"parts": [{"text": processed_text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name},
                }
            },
        },
    }


@dataclass(frozen=True)
class _RateLimitResult:
    ok: bool
    retry_after_seconds: int


class TTSAppService:
    """
    聚合网关 TTS 服务：
    - 复用 ProviderSelector 进行多 provider 选路；
    - 不落库、不走 OSS，仅做直返二进制音频；
    - 使用 Redis 做短期缓存（避免重复播放重复计费）；
    - 失败按候选 provider 逐个尝试。
    """

    def __init__(
        self,
        *,
        client: CurlCffiClient,
        redis: Redis,
        db: Session,
        api_key: AuthenticatedAPIKey,
    ) -> None:
        self.client = client
        self.redis = redis
        self.db = db
        self.api_key = api_key
        self.routing_state = RoutingStateService(redis=redis)
        self.provider_selector = ProviderSelector(client=client, redis=redis, db=db, routing_state=self.routing_state)

    def preprocess_text(self, text: str) -> str:
        raw = str(text or "")
        raw = _MARKDOWN_LINK_RE.sub(r"\1", raw)
        raw = _MARKDOWN_CHARS_RE.sub("", raw)
        raw = _HTML_TAG_RE.sub("", raw)
        raw = unicodedata.normalize("NFKC", raw)
        return raw.strip()

    async def _rate_limit(self, *, user_id: str, request_id: str) -> _RateLimitResult:
        if self.redis is object:
            return _RateLimitResult(ok=True, retry_after_seconds=0)

        now = int(time.time())
        minute = now // 60
        user_key = f"tts:rl:user:{user_id}:{minute}"
        global_key = f"tts:rl:global:{minute}"
        expires = 120
        try:
            if hasattr(self.redis, "pipeline"):
                pipe = self.redis.pipeline()
                pipe.incr(user_key)
                pipe.expire(user_key, expires)
                pipe.incr(global_key)
                pipe.expire(global_key, expires)
                user_count, _, global_count, _ = await pipe.execute()
            else:
                user_count = await self.redis.incr(user_key)
                await self.redis.expire(user_key, expires)
                global_count = await self.redis.incr(global_key)
                await self.redis.expire(global_key, expires)
        except Exception:  # pragma: no cover
            logger.debug("tts: rate limit check failed (request_id=%s)", request_id, exc_info=True)
            return _RateLimitResult(ok=True, retry_after_seconds=0)

        if int(user_count or 0) > _TTS_USER_LIMIT_PER_MINUTE:
            return _RateLimitResult(ok=False, retry_after_seconds=60 - (now % 60))
        if int(global_count or 0) > _TTS_GLOBAL_LIMIT_PER_MINUTE:
            return _RateLimitResult(ok=False, retry_after_seconds=60 - (now % 60))
        return _RateLimitResult(ok=True, retry_after_seconds=0)

    def _cache_key(self, *, user_id: str, request: SpeechRequest, processed_text: str) -> str:
        text_hash = hashlib.sha256(processed_text.encode("utf-8")).hexdigest()
        ref = str(getattr(request, "reference_audio_url", None) or "").strip()
        ref_hash = hashlib.sha256(ref.encode("utf-8")).hexdigest() if ref else ""
        raw = (
            f"{user_id}:{request.model}:{request.voice}:{request.speed}:{request.response_format}:"
            f"{getattr(request, 'input_type', 'text')}:{getattr(request, 'locale', None)}:"
            f"{getattr(request, 'pitch', None)}:{getattr(request, 'volume', None)}:{ref_hash}:{text_hash}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"tts:cache:{digest}"

    async def _load_cached_audio(self, *, key: str) -> bytes | None:
        if self.redis is object:
            return None
        try:
            cached = await self.redis.get(key)
        except Exception:  # pragma: no cover
            return None
        if not cached:
            return None
        return bytes(cached)

    async def _store_cached_audio(self, *, key: str, data: bytes) -> None:
        if self.redis is object:
            return
        try:
            await self.redis.set(key, data, ex=_CACHE_TTL_SECONDS)
        except Exception:  # pragma: no cover
            logger.debug("tts: failed to store cache key=%s", key, exc_info=True)

    async def _acquire_lock(self, *, key: str) -> bool:
        if self.redis is object:
            return True
        try:
            return bool(await self.redis.set(key, "1", nx=True, ex=_LOCK_TTL_SECONDS))
        except Exception:  # pragma: no cover
            return True

    async def _release_lock(self, *, key: str) -> None:
        if self.redis is object:
            return
        try:
            await self.redis.delete(key)
        except Exception:  # pragma: no cover
            pass

    def _ensure_cacheable(self, request: SpeechRequest) -> bool:
        fmt = str(request.response_format or "").strip().lower()
        return fmt in _CACHEABLE_FORMATS

    async def stream_speech(self, request: SpeechRequest) -> AsyncIterator[bytes]:
        request_id = uuid.uuid4().hex

        input_type = str(getattr(request, "input_type", "text") or "text").strip().lower()
        if input_type == "ssml":
            processed_text = str(request.input or "").strip()
        else:
            processed_text = self.preprocess_text(request.input)
        if not processed_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "input 不能为空"},
            )

        rate = await self._rate_limit(user_id=str(self.api_key.user_id), request_id=request_id)
        if not rate.ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"message": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": str(max(1, int(rate.retry_after_seconds)))},
            )

        try:
            ensure_account_usable(self.db, user_id=self.api_key.user_id)
        except InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "code": "CREDIT_NOT_ENOUGH",
                    "message": str(exc),
                    "balance": exc.balance,
                },
            ) from exc

        effective_provider_ids = self._resolve_effective_provider_ids()
        if not effective_provider_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "当前用户暂无可用的提供商"},
            )

        cache_key = self._cache_key(
            user_id=str(self.api_key.user_id),
            request=request,
            processed_text=processed_text,
        )
        cached = await self._load_cached_audio(key=cache_key)
        if cached is not None:
            for i in range(0, len(cached), _CACHE_CHUNK_SIZE):
                yield cached[i : i + _CACHE_CHUNK_SIZE]
            return

        lock_key = f"tts:lock:{cache_key}"
        acquired = await self._acquire_lock(key=lock_key)
        if not acquired:
            # 等待并复用其他请求产物（最多 30 秒）
            for _ in range(30):
                await asyncio.sleep(1)
                cached = await self._load_cached_audio(key=cache_key)
                if cached is not None:
                    for i in range(0, len(cached), _CACHE_CHUNK_SIZE):
                        yield cached[i : i + _CACHE_CHUNK_SIZE]
                    return
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "TTS 正在生成，请稍后重试"},
            )

        try:
            try:
                selection = await self.provider_selector.select(
                    requested_model=request.model,
                    lookup_model_id=request.model,
                    api_style="openai",
                    effective_provider_ids=effective_provider_ids,
                    user_id=uuid.UUID(str(self.api_key.user_id)),
                    is_superuser=bool(self.api_key.is_superuser),
                )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"message": "模型选路失败"},
                ) from exc

            caps = set(getattr(selection.logical_model, "capabilities", None) or [])
            if ModelCapability.AUDIO not in caps:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "该模型不支持音频（audio）能力"},
                )

            ordered_candidates = list(selection.ordered_candidates or [])
            if ordered_candidates:
                provider_ids = {c.upstream.provider_id for c in ordered_candidates}
                model_ids = {c.upstream.model_id for c in ordered_candidates}
                requires_map: dict[tuple[str, str], bool] = {}
                try:
                    rows = self.db.execute(
                        select(Provider.provider_id, ProviderModel.model_id, ProviderModel.metadata_json)
                        .select_from(ProviderModel)
                        .join(Provider, ProviderModel.provider_id == Provider.id)
                        .where(Provider.provider_id.in_(list(provider_ids)))
                        .where(ProviderModel.model_id.in_(list(model_ids)))
                    ).all()
                    for pid, mid, meta in rows:
                        if isinstance(pid, str) and isinstance(mid, str):
                            requires_map[(pid, mid)] = _model_requires_reference_audio(meta)
                except Exception:
                    logger.warning("tts: failed to load provider model metadata for reference-audio filtering", exc_info=True)

                if request.reference_audio_url is None:
                    filtered = [
                        c for c in ordered_candidates if not requires_map.get((c.upstream.provider_id, c.upstream.model_id), False)
                    ]
                    if filtered:
                        ordered_candidates = filtered
                    else:
                        required_by: list[dict[str, str]] = []
                        for c in ordered_candidates:
                            if requires_map.get((c.upstream.provider_id, c.upstream.model_id), False):
                                required_by.append(
                                    {"provider": c.upstream.provider_id, "model_id": c.upstream.model_id}
                                )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={
                                "message": "该请求缺少 reference_audio_url，无法路由到需要参考音频的 TTS 上游",
                                "missing_field": "reference_audio_url",
                                "required_by": required_by,
                            },
                        )

            cacheable = self._ensure_cacheable(request=request)
            cache_buffer = bytearray()
            cache_overflow = False

            last_status: int | None = None
            last_error_detail: Any | None = None

            for scored in ordered_candidates:
                cand = scored.upstream
                provider_id = cand.provider_id
                model_id = cand.model_id

                cooldown = await self.routing_state.get_failure_cooldown_status(provider_id)
                if cooldown.should_skip:
                    continue

                cfg = provider_config.get_provider_config(provider_id, session=self.db)
                if cfg is None:
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_detail = {"message": f"Provider '{provider_id}' is not configured"}
                    await self.routing_state.increment_provider_failure(provider_id)
                    continue

                try:
                    key_selection = await acquire_provider_key(cfg, self.redis)
                except NoAvailableProviderKey as exc:
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_detail = {"message": str(exc)}
                    await self.routing_state.increment_provider_failure(provider_id)
                    continue

                start = time.perf_counter()
                try:
                    if _is_google_native_provider_base_url(str(cfg.base_url)):
                        async for chunk in self._call_gemini_tts(
                            provider_id=provider_id,
                            provider_cfg=cfg,
                            model_id=str(model_id),
                            api_key=key_selection.key,
                            request=request,
                            processed_text=processed_text,
                        ):
                            if cacheable and not cache_overflow:
                                if len(cache_buffer) + len(chunk) <= _MAX_CACHE_BYTES:
                                    cache_buffer.extend(chunk)
                                else:
                                    cache_overflow = True
                            yield chunk
                    else:
                        async for chunk in self._call_openai_compatible_tts(
                            provider_id=provider_id,
                            provider_cfg=cfg,
                            provider_model_id=str(model_id),
                            api_key=key_selection.key,
                            request=request,
                            processed_text=processed_text,
                        ):
                            if cacheable and not cache_overflow:
                                if len(cache_buffer) + len(chunk) <= _MAX_CACHE_BYTES:
                                    cache_buffer.extend(chunk)
                                else:
                                    cache_overflow = True
                            yield chunk

                    latency_ms = (time.perf_counter() - start) * 1000.0
                    record_key_success(key_selection, redis=self.redis)
                    self.routing_state.record_success(
                        selection.logical_model.logical_id,
                        provider_id,
                        float(getattr(cand, "base_weight", 1.0) or 1.0),
                    )
                    await self.routing_state.clear_provider_failure(provider_id)
                    record_provider_call_metric(
                        self.db,
                        provider_id=provider_id,
                        logical_model=str(selection.logical_model.logical_id),
                        transport=str(getattr(cfg, "transport", "http") or "http"),
                        is_stream=True,
                        user_id=uuid.UUID(str(self.api_key.user_id)),
                        api_key_id=uuid.UUID(str(self.api_key.id)),
                        success=True,
                        latency_ms=float(latency_ms),
                        status_code=200,
                    )

                    if cacheable and not cache_overflow and cache_buffer:
                        await self._store_cached_audio(key=cache_key, data=bytes(cache_buffer))
                    return

                except HTTPException as exc:
                    last_status = int(exc.status_code)
                    if isinstance(exc.detail, dict):
                        last_error_detail = exc.detail
                    else:
                        last_error_detail = {"message": str(exc.detail)}
                    record_key_failure(
                        key_selection,
                        retryable=not (400 <= int(exc.status_code) < 500),
                        status_code=last_status,
                        redis=self.redis,
                    )
                    await self.routing_state.increment_provider_failure(provider_id)
                    self.routing_state.record_failure(
                        selection.logical_model.logical_id,
                        provider_id,
                        float(getattr(cand, "base_weight", 1.0) or 1.0),
                        retryable=True,
                    )
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    record_provider_call_metric(
                        self.db,
                        provider_id=provider_id,
                        logical_model=str(selection.logical_model.logical_id),
                        transport=str(getattr(cfg, "transport", "http") or "http"),
                        is_stream=True,
                        user_id=uuid.UUID(str(self.api_key.user_id)),
                        api_key_id=uuid.UUID(str(self.api_key.id)),
                        success=False,
                        latency_ms=float(latency_ms),
                        status_code=last_status,
                    )
                    continue
                except Exception as exc:
                    last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    last_error_detail = {"message": str(exc)}
                    record_key_failure(
                        key_selection, retryable=True, status_code=None, redis=self.redis
                    )
                    await self.routing_state.increment_provider_failure(provider_id)
                    self.routing_state.record_failure(
                        selection.logical_model.logical_id,
                        provider_id,
                        float(getattr(cand, "base_weight", 1.0) or 1.0),
                        retryable=True,
                    )
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    record_provider_call_metric(
                        self.db,
                        provider_id=provider_id,
                        logical_model=str(selection.logical_model.logical_id),
                        transport=str(getattr(cfg, "transport", "http") or "http"),
                        is_stream=True,
                        user_id=uuid.UUID(str(self.api_key.user_id)),
                        api_key_id=uuid.UUID(str(self.api_key.id)),
                        success=False,
                        latency_ms=float(latency_ms),
                        status_code=None,
                    )
                    continue

            raise HTTPException(
                status_code=int(last_status or status.HTTP_503_SERVICE_UNAVAILABLE),
                detail=(
                    last_error_detail
                    if isinstance(last_error_detail, dict) and last_error_detail
                    else {"message": "所有提供商均不可用"}
                ),
            )
        finally:
            await self._release_lock(key=lock_key)

    async def generate_speech_bytes(self, request: SpeechRequest) -> bytes:
        """
        生成完整音频并一次性返回 bytes。

        说明：StreamingResponse 会在真正拉到上游数据前就发送 200 + Content-Type。
        若上游随后失败，客户端可能收到 200 但无音频数据（浏览器播放会报 NotSupportedError）。
        这里通过“先生成再返回”的方式，确保失败能正确以 4xx/5xx 响应返回。
        """
        buf = bytearray()
        async for chunk in self.stream_speech(request):
            if not chunk:
                continue
            if len(buf) + len(chunk) > _MAX_CACHE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={"message": "TTS 音频输出过大"},
                )
            buf.extend(chunk)

        if not buf:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "TTS 未返回音频数据"},
            )
        return bytes(buf)

    def _resolve_effective_provider_ids(self) -> set[str]:
        accessible_provider_ids = get_accessible_provider_ids(self.db, self.api_key.user_id)
        if not accessible_provider_ids:
            return set()

        effective_provider_ids = set(accessible_provider_ids)
        if self.api_key.has_provider_restrictions:
            allowed = {pid for pid in self.api_key.allowed_provider_ids if pid}
            effective_provider_ids &= allowed
        return effective_provider_ids

    async def _call_openai_compatible_tts(
        self,
        *,
        provider_id: str,
        provider_cfg,
        provider_model_id: str,
        api_key: str,
        request: SpeechRequest,
        processed_text: str,
    ) -> AsyncIterator[bytes]:
        path = _derive_openai_audio_speech_path(provider_cfg)
        base_url = str(getattr(provider_cfg, "base_url", "") or "").rstrip("/")
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": f"Provider '{provider_id}' base_url is empty"},
            )
        url = f"{base_url}/{path.lstrip('/')}"
        allow_extensions = not _is_openai_official_provider_base_url(base_url)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Authorization": f"Bearer {api_key}",
        }
        custom_headers = getattr(provider_cfg, "custom_headers", None)
        if isinstance(custom_headers, dict) and custom_headers:
            headers.update({str(k): str(v) for k, v in custom_headers.items()})

        payload = _build_openai_compatible_tts_payload(
            provider_model_id=provider_model_id,
            processed_text=processed_text,
            request=request,
            allow_extensions=allow_extensions,
        )

        async with self.client.stream("POST", url, headers=headers, json=payload) as resp:
            if int(getattr(resp, "status_code", 0) or 0) >= 400:
                body = await resp.aread()
                text = body.decode("utf-8", errors="ignore")
                logger.warning(
                    "tts: upstream http error provider=%s status=%s url=%s body=%s",
                    provider_id,
                    getattr(resp, "status_code", None),
                    url,
                    text,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "message": f"upstream HTTP {resp.status_code}",
                        "provider": provider_id,
                        "upstream_body": text[:800],
                    },
                )
            async for chunk in resp.aiter_bytes(chunk_size=_CACHE_CHUNK_SIZE):
                if chunk:
                    yield bytes(chunk)

    async def _call_gemini_tts(
        self,
        *,
        provider_id: str,
        provider_cfg,
        model_id: str,
        api_key: str,
        request: SpeechRequest,
        processed_text: str,
    ) -> AsyncIterator[bytes]:
        """
        Gemini TTS：通过 generateContent 返回 inlineData（base64）。
        说明：
        - 本网关不做音频转码；
        - 若上游返回容器格式（如 audio/wav/mp3/aac/ogg/flac/aiff），会要求与请求的 response_format 匹配；
        - 若上游返回 PCM（audio/L16 或 audio/pcm，或不带 mimeType），支持：
          - response_format=pcm：原样直返
          - response_format=wav：仅封装 WAV 头（不重采样/不转码）
        """
        requested_fmt = str(request.response_format or "").strip().lower()

        base_url = str(getattr(provider_cfg, "base_url", "") or "").rstrip("/")
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": f"Provider '{provider_id}' base_url is empty"},
            )

        url = f"{base_url}/v1beta/models/{model_id}:generateContent"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-api-key": api_key,
        }
        custom_headers = getattr(provider_cfg, "custom_headers", None)
        if isinstance(custom_headers, dict) and custom_headers:
            headers.update({str(k): str(v) for k, v in custom_headers.items()})

        payload = _build_gemini_tts_payload(request=request, processed_text=processed_text)

        resp = await self.client.post(url, headers=headers, json=payload)
        if int(getattr(resp, "status_code", 0) or 0) >= 400:
            body = await resp.acontent()
            text = body.decode("utf-8", errors="ignore")
            logger.warning(
                "tts: gemini upstream http error provider=%s status=%s url=%s body=%s",
                provider_id,
                getattr(resp, "status_code", None),
                url,
                text,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": f"upstream HTTP {resp.status_code}", "provider": provider_id},
            )

        raw = await resp.acontent()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "Gemini 响应解析失败", "provider": provider_id},
            ) from exc

        inline = None
        try:
            inline = (
                parsed["candidates"][0]["content"]["parts"][0]["inlineData"]
                if isinstance(parsed, dict)
                else None
            )
        except Exception:
            inline = None

        if not isinstance(inline, dict):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "Gemini 未返回 inlineData", "provider": provider_id},
            )

        mime_type = str(inline.get("mimeType") or inline.get("mime_type") or "")
        b64data = inline.get("data")
        if not isinstance(b64data, str) or not b64data:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "Gemini inlineData.data 为空", "provider": provider_id},
            )

        try:
            audio_bytes = base64.b64decode(b64data)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "Gemini 音频 base64 解码失败", "provider": provider_id},
            ) from exc

        primary_mime, params = _parse_mime_type(mime_type)
        returned_fmt = _normalize_audio_format_from_mime(primary_mime)

        # 1) 上游返回已编码的容器格式：要求严格匹配，不做转码。
        if returned_fmt in {"wav", "mp3", "aac", "opus", "ogg", "flac", "aiff"}:
            if requested_fmt != returned_fmt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": (
                            f"Gemini 返回 {primary_mime or 'audio/*'}，"
                            f"请使用 response_format={returned_fmt}"
                        )
                    },
                )
            yield audio_bytes
            return

        # 2) 上游返回 PCM（或未给 mimeType）：允许直返 pcm 或封装 wav。
        if returned_fmt in {"pcm", None}:
            if requested_fmt == "pcm":
                yield audio_bytes
                return
            if requested_fmt == "wav":
                rate_raw = params.get("rate")
                channels_raw = params.get("channels")
                try:
                    rate = int(rate_raw) if rate_raw else 24000
                except ValueError:
                    rate = 24000
                try:
                    channels = int(channels_raw) if channels_raw else 1
                except ValueError:
                    channels = 1

                try:
                    wav_bytes = _wrap_pcm_as_wav(
                        audio_bytes, sample_rate=rate, channels=channels, sample_width_bytes=2
                    )
                except Exception as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={"message": "PCM 封装 WAV 失败", "provider": provider_id},
                    ) from exc
                yield wav_bytes
                return

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": (
                        "Gemini 返回 PCM 音频，"
                        "请使用 response_format=pcm 或 response_format=wav（网关仅封装 WAV 头）"
                    )
                },
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Gemini 暂不支持的 mimeType: {mime_type}"},
        )


__all__ = ["TTSAppService", "_content_type_for_format", "_extract_text_from_message_content"]
