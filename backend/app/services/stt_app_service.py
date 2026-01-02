from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.chat.header_builder import build_upstream_headers
from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.auth import AuthenticatedAPIKey
from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.provider import config as provider_config
from app.provider.key_pool import (
    NoAvailableProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)
from app.provider.utils import derive_openai_audio_transcriptions_path, is_google_native_provider_base_url
from app.schemas.model import ModelCapability
from app.services.chat_routing_service import _apply_upstream_path_override, _is_retryable_upstream_status
from app.services.credit_service import InsufficientCreditsError, ensure_account_usable
from app.services.metrics_service import record_provider_call_metric
from app.services.user_provider_service import get_accessible_provider_ids

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


@dataclass(frozen=True)
class TranscriptionOutput:
    text: str


def _extract_openai_transcription_text(payload: Any) -> str | None:
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        out = payload["text"].strip()
        return out or None
    if isinstance(payload, str):
        out = payload.strip()
        return out or None
    return None


class STTAppService:
    """
    聚合网关 STT（Speech-to-Text）服务：

    - 复用 ProviderSelector 进行多 provider 选路；
    - 复用 KeyPool 与失败冷却；
    - 以 OpenAI-compatible `/v1/audio/transcriptions` 上游 API 为主（multipart/form-data）。
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

    async def transcribe_bytes(
        self,
        *,
        model: str,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
        prompt: str | None = None,
        request_id: str | None = None,
    ) -> TranscriptionOutput:
        request_id = str(request_id or uuid.uuid4().hex)
        logical_model = str(model or "").strip()
        if not logical_model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "model 字段不能为空"},
            )
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "空音频文件"},
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

        accessible_provider_ids = get_accessible_provider_ids(self.db, self.api_key.user_id)
        if not accessible_provider_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "当前用户暂无可用的提供商"},
            )

        effective_provider_ids = set(accessible_provider_ids)
        if self.api_key.has_provider_restrictions:
            allowed = {pid for pid in self.api_key.allowed_provider_ids if pid}
            effective_provider_ids &= allowed
            if not effective_provider_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"message": "当前 API Key 未允许访问任何可用的提供商"},
                )

        selection = await self.provider_selector.select(
            requested_model=logical_model,
            lookup_model_id=logical_model,
            api_style="openai",
            effective_provider_ids=effective_provider_ids,
            user_id=self.api_key.user_id,
            is_superuser=bool(self.api_key.is_superuser),
        )

        caps = set(getattr(selection.logical_model, "capabilities", None) or [])
        if ModelCapability.AUDIO not in caps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "该模型不支持音频（audio）能力"},
            )

        last_status: int | None = None
        last_error_detail: dict[str, Any] | None = None

        for scored in list(selection.ordered_candidates or []):
            cand = scored.upstream
            provider_id = cand.provider_id
            model_id = cand.model_id
            start = time.perf_counter()

            cooldown = await self.routing_state.get_failure_cooldown_status(provider_id)
            if cooldown.should_skip:
                continue

            cfg = provider_config.get_provider_config(provider_id, session=self.db)
            if cfg is None:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error_detail = {"message": f"Provider '{provider_id}' is not configured"}
                continue

            base_url = str(getattr(cfg, "base_url", "") or "").rstrip("/")
            if not base_url:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error_detail = {"message": f"Provider '{provider_id}' base_url is empty"}
                continue

            if is_google_native_provider_base_url(base_url):
                last_status = status.HTTP_400_BAD_REQUEST
                last_error_detail = {"message": "当前 STT 仅支持 OpenAI-compatible 上游（暂不支持 Google 原生地址）"}
                continue

            try:
                key_selection = await acquire_provider_key(cfg, self.redis)
            except NoAvailableProviderKey as exc:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error_detail = {"message": str(exc)}
                continue

            try:
                transcriptions_path = derive_openai_audio_transcriptions_path(
                    getattr(cfg, "chat_completions_path", None)
                )
                url = _apply_upstream_path_override(cand.endpoint, transcriptions_path)

                headers = build_upstream_headers(
                    key_selection.key,
                    cfg,
                    call_style="openai",
                    is_stream=False,
                )
                headers.pop("Content-Type", None)
                headers["Accept"] = "application/json"

                fields: dict[str, Any] = {
                    "model": (None, str(model_id)),
                    "file": (str(filename or "audio.wav"), bytes(audio_bytes), str(content_type or "application/octet-stream")),
                }
                lang = str(language or "").strip()
                if lang:
                    fields["language"] = (None, lang)
                pr = str(prompt or "").strip()
                if pr:
                    fields["prompt"] = (None, pr)

                resp = await self.client.post(url, headers=headers, files=fields)
                if int(getattr(resp, "status_code", 0) or 0) >= 400:
                    retryable = _is_retryable_upstream_status(provider_id, int(resp.status_code))
                    record_key_failure(
                        key_selection,
                        retryable=retryable,
                        status_code=int(resp.status_code),
                        redis=self.redis,
                    )
                    if retryable and int(resp.status_code) in (500, 502, 503, 504, 429, 404, 405):
                        await self.routing_state.increment_provider_failure(provider_id)
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={"message": f"Upstream error {resp.status_code}"},
                        )
                    body = getattr(resp, "text", "")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={"message": f"Upstream error {resp.status_code}", "upstream_body": str(body)[:800]},
                    )

                try:
                    payload = resp.json()
                except Exception:
                    payload = getattr(resp, "text", "")

                text = _extract_openai_transcription_text(payload)
                if not text:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={"message": "Upstream returned empty transcription"},
                    )

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
                    is_stream=False,
                    user_id=uuid.UUID(str(self.api_key.user_id)),
                    api_key_id=uuid.UUID(str(self.api_key.id)),
                    success=True,
                    latency_ms=float(latency_ms),
                    status_code=200,
                )

                return TranscriptionOutput(text=text)
            except HTTPException as exc:
                last_status = int(exc.status_code)
                detail = exc.detail
                last_error_detail = detail if isinstance(detail, dict) else {"message": str(detail)}
                latency_ms = (time.perf_counter() - start) * 1000.0
                record_provider_call_metric(
                    self.db,
                    provider_id=provider_id,
                    logical_model=str(selection.logical_model.logical_id),
                    transport=str(getattr(cfg, "transport", "http") or "http"),
                    is_stream=False,
                    user_id=uuid.UUID(str(self.api_key.user_id)),
                    api_key_id=uuid.UUID(str(self.api_key.id)),
                    success=False,
                    latency_ms=float(latency_ms),
                    status_code=last_status,
                )
                logger.debug("stt: candidate failed provider=%s status=%s request_id=%s", provider_id, last_status, request_id, exc_info=True)
                continue
            except Exception as exc:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error_detail = {"message": str(exc)}
                latency_ms = (time.perf_counter() - start) * 1000.0
                record_provider_call_metric(
                    self.db,
                    provider_id=provider_id,
                    logical_model=str(selection.logical_model.logical_id),
                    transport=str(getattr(cfg, "transport", "http") or "http"),
                    is_stream=False,
                    user_id=uuid.UUID(str(self.api_key.user_id)),
                    api_key_id=uuid.UUID(str(self.api_key.id)),
                    success=False,
                    latency_ms=float(latency_ms),
                    status_code=None,
                )
                logger.debug("stt: candidate error provider=%s request_id=%s", provider_id, request_id, exc_info=True)
                continue

        raise HTTPException(
            status_code=int(last_status or status.HTTP_503_SERVICE_UNAVAILABLE),
            detail=last_error_detail or {"message": "所有提供商均不可用"},
        )


__all__ = ["STTAppService", "TranscriptionOutput"]

