from __future__ import annotations

import base64
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.api.v1.chat.header_builder import build_upstream_headers
from app.auth import AuthenticatedAPIKey
from app.errors import forbidden
from app.logging_config import logger
from app.provider import config as provider_config
from app.provider.key_pool import (
    NoAvailableProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)
from app.schemas import ModelCapability
from app.schemas.video import VideoGenerationRequest, VideoGenerationResponse, VideoObject
from app.services.chat_routing_service import _apply_upstream_path_override, _is_retryable_upstream_status
from app.services.credit_service import InsufficientCreditsError, ensure_account_usable
from app.services.video_storage_service import build_signed_video_url, store_video_bytes
from app.services.user_provider_service import get_accessible_provider_ids


video_debug_logger = logging.getLogger("apiproxy.video_debug")


class _RetryableCandidateError(Exception):
    pass


_OPENAI_SORA_ALLOWED_SECONDS: set[int] = {4, 8, 12}
_OPENAI_SORA_ALLOWED_SIZES: set[str] = {"720x1280", "1280x720", "1024x1792", "1792x1024"}


def _is_google_native_provider_base_url(base_url: str) -> bool:
    raw = str(base_url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlsplit(raw)
    except Exception:
        return False
    return str(parsed.netloc or "").lower() == "generativelanguage.googleapis.com"


def _google_v1beta_base(base_url: str) -> str:
    base = str(base_url or "").rstrip("/")
    if base.endswith("/v1beta"):
        return base
    return f"{base}/v1beta"


def _derive_openai_videos_path(provider_chat_path: str | None) -> str:
    """
    从 chat_completions_path 推导对应的 /videos 路径，以兼容 base_url 是否自带 /v1。
    """
    raw = str(provider_chat_path or "/v1/chat/completions").strip() or "/v1/chat/completions"
    lowered = raw.lower()
    if "chat/completions" in lowered:
        prefix = raw[: lowered.rfind("chat/completions")]
        return f"{prefix}videos".replace("//", "/")
    return "/v1/videos"


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if key in base and isinstance(base.get(key), dict) and isinstance(value, dict):
            _deep_merge_dict(base[key], value)  # type: ignore[index]
            continue
        base[key] = value
    return base


def _get_vendor_extra(request: VideoGenerationRequest, vendor: str) -> dict[str, Any] | None:
    extra = getattr(request, "extra_body", None)
    if not isinstance(extra, dict):
        return None
    payload = extra.get(vendor)
    if not isinstance(payload, dict):
        return None
    return payload


def _parse_size(size: str | None) -> tuple[int, int] | None:
    if not size:
        return None
    text = str(size).strip().lower()
    if not text or "x" not in text:
        return None
    w_raw, _, h_raw = text.partition("x")
    try:
        w = int(w_raw)
        h = int(h_raw)
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return w, h


def _map_size_to_aspect_ratio(size: str | None) -> str | None:
    parsed = _parse_size(size)
    if not parsed:
        return None
    w, h = parsed

    def _gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a

    g = _gcd(w, h)
    rw, rh = w // g, h // g
    known = {
        (1, 1): "1:1",
        (9, 16): "9:16",
        (16, 9): "16:9",
        (4, 3): "4:3",
        (3, 4): "3:4",
        (21, 9): "21:9",
    }
    return known.get((rw, rh))


def _map_size_to_resolution(size: str | None) -> str | None:
    parsed = _parse_size(size)
    if not parsed:
        return None
    w, h = parsed
    max_dim = max(w, h)
    min_dim = min(w, h)
    if max_dim >= 1920 or min_dim >= 1080:
        return "1080p"
    return "720p"


def _choose_openai_sora_size_from_hints(
    *,
    size: str | None,
    aspect_ratio: str | None,
    resolution: str | None,
) -> str | None:
    """
    OpenAI Sora 只接受枚举 size 值；当用户未提供 size 时，尝试用 aspect_ratio/resolution 推导。
    """
    if isinstance(size, str) and size.strip():
        # 即使不在允许列表，也原样透传给上游，让上游做校验并返回明确错误。
        return size.strip()

    ar = str(aspect_ratio or "").strip()
    res = str(resolution or "").strip()

    # Default to 720p when only aspect ratio is provided.
    if not res and ar:
        res = "720p"

    if ar == "16:9" and res == "720p":
        return "1280x720"
    if ar == "9:16" and res == "720p":
        return "720x1280"
    if ar == "16:9" and res == "1080p":
        return "1792x1024"
    if ar == "9:16" and res == "1080p":
        return "1024x1792"

    # 1:1 / 4:3 / 3:4 / 21:9 等比例在 OpenAI 文档允许的 size 中没有直接对应，留给调用方显式指定 size。
    return None


def _build_openai_videos_multipart_fields(
    *,
    request: VideoGenerationRequest,
    model_id: str,
) -> dict[str, tuple[None, str]]:
    form: dict[str, str] = {"prompt": str(request.prompt or ""), "model": str(model_id or "")}

    size = _choose_openai_sora_size_from_hints(
        size=getattr(request, "size", None),
        aspect_ratio=getattr(request, "aspect_ratio", None),
        resolution=getattr(request, "resolution", None),
    )
    if isinstance(size, str) and size.strip():
        form["size"] = size.strip()

    seconds = getattr(request, "seconds", None)
    if seconds is not None:
        form["seconds"] = str(int(seconds))

    image_url = getattr(request, "image_url", None)
    if isinstance(image_url, str) and image_url.strip():
        form["image_url"] = image_url.strip()

    audio_url = getattr(request, "audio_url", None)
    if isinstance(audio_url, str) and audio_url.strip():
        form["audio_url"] = audio_url.strip()

    return {k: (None, v) for k, v in form.items() if isinstance(k, str) and v is not None}


def _build_google_veo_predict_payload(*, request: VideoGenerationRequest) -> dict[str, Any]:
    parameters: dict[str, Any] = {}

    aspect_ratio = getattr(request, "aspect_ratio", None) or _map_size_to_aspect_ratio(getattr(request, "size", None))
    if aspect_ratio:
        parameters["aspectRatio"] = aspect_ratio

    negative_prompt = getattr(request, "negative_prompt", None)
    if isinstance(negative_prompt, str) and negative_prompt.strip():
        parameters["negativePrompt"] = negative_prompt.strip()

    # 其余字段（seed/fps/num_outputs/generate_audio/enhance_prompt/duration 等）
    # 各上游差异较大，默认不强行映射；需要时通过 extra_body.google.parameters 显式配置。

    upstream_payload: dict[str, Any] = {"instances": [{"prompt": request.prompt}], "parameters": parameters}
    vendor_extra = _get_vendor_extra(request, "google")
    if vendor_extra:
        _deep_merge_dict(upstream_payload, vendor_extra)
    return upstream_payload


def _extract_openai_video_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    vid = payload.get("id")
    if isinstance(vid, str) and vid.strip():
        return vid.strip()
    return None


def _extract_openai_video_status(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    st = payload.get("status")
    if isinstance(st, str) and st.strip():
        return st.strip().lower()
    return None


def _extract_google_operation_name(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip().lstrip("/")
    return None


def _extract_google_video_download_uri(payload: Any) -> str | None:
    """
    从 operations.get 的终态 payload 中提取下载 URI。

    参考官方 REST 示例：
    .response.generateVideoResponse.generatedSamples.video.uri
    """
    if not isinstance(payload, dict):
        return None
    resp = payload.get("response")
    if not isinstance(resp, dict):
        return None
    gen = resp.get("generateVideoResponse")
    if not isinstance(gen, dict):
        return None
    samples = gen.get("generatedSamples")
    if isinstance(samples, dict):
        video = samples.get("video")
        if isinstance(video, dict) and isinstance(video.get("uri"), str) and video["uri"].strip():
            return video["uri"].strip()
    if isinstance(samples, list):
        for item in samples:
            if not isinstance(item, dict):
                continue
            video = item.get("video")
            if isinstance(video, dict) and isinstance(video.get("uri"), str) and video["uri"].strip():
                return video["uri"].strip()
    return None


class VideoAppService:
    """
    视频生成入口：复用 ProviderSelector 的模型解析与候选调度，按候选 provider 逐个尝试。

    当前支持：
    - OpenAI-compatible：/v1/videos（Sora）
    - Gemini Developer API：Veo 的 :predictLongRunning + operations poll
    """

    def __init__(
        self,
        *,
        client: Any,
        redis: Redis,
        db: Session,
        api_key: AuthenticatedAPIKey,
    ) -> None:
        self.client = client
        self.redis = redis
        self.db = db
        self.api_key = api_key
        self.routing_state = RoutingStateService(redis=redis)
        self.provider_selector = ProviderSelector(
            client=client, redis=redis, db=db, routing_state=self.routing_state
        )

    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        model = str(getattr(request, "model", "") or "").strip()
        if not model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "model 字段不能为空"},
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
            raise forbidden("当前用户暂无可用的提供商")

        effective_provider_ids = set(accessible_provider_ids)
        if self.api_key.has_provider_restrictions:
            allowed = {pid for pid in self.api_key.allowed_provider_ids if pid}
            effective_provider_ids &= allowed
            if not effective_provider_ids:
                raise forbidden(
                    "当前 API Key 未允许访问任何可用的提供商",
                    details={
                        "api_key_id": str(self.api_key.id),
                        "allowed_provider_ids": self.api_key.allowed_provider_ids,
                    },
                )

        selection = await self.provider_selector.select(
            requested_model=model,
            lookup_model_id=model,
            api_style="openai",
            effective_provider_ids=effective_provider_ids,
            user_id=self.api_key.user_id,
            is_superuser=bool(self.api_key.is_superuser),
        )

        caps = set(getattr(selection.logical_model, "capabilities", None) or [])
        if ModelCapability.VIDEO_GENERATION not in caps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "该模型不支持视频生成（video_generation）能力"},
            )

        return await self._generate_with_mixed_lanes(request, selection)

    async def _generate_with_mixed_lanes(self, request: VideoGenerationRequest, selection) -> VideoGenerationResponse:
        last_status: int | None = None
        last_error: str | None = None
        skipped_count = 0

        for scored in selection.ordered_candidates:
            cand = scored.upstream
            provider_id = cand.provider_id
            model_id = cand.model_id

            cooldown = await self.routing_state.get_failure_cooldown_status(provider_id)
            if cooldown.should_skip:
                skipped_count += 1
                continue

            cfg = provider_config.get_provider_config(provider_id, session=self.db)
            if cfg is None:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error = f"Provider '{provider_id}' is not configured"
                continue

            base_url = str(getattr(cfg, "base_url", "") or "").rstrip("/")
            if not base_url:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error = f"Provider '{provider_id}' base_url is empty"
                continue

            try:
                key_selection = await acquire_provider_key(cfg, self.redis)
            except NoAvailableProviderKey as exc:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error = str(exc)
                continue

            try:
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http_client:
                    if _is_google_native_provider_base_url(base_url):
                        resp = await self._call_google_veo_predict_long_running(
                            http_client=http_client,
                            request=request,
                            selection=selection,
                            cfg=cfg,
                            provider_id=provider_id,
                            model_id=str(model_id or ""),
                            base_url=base_url,
                            key_selection=key_selection,
                        )
                    else:
                        resp = await self._call_openai_videos(
                            http_client=http_client,
                            request=request,
                            selection=selection,
                            cfg=cfg,
                            provider_id=provider_id,
                            model_id=str(model_id or ""),
                            endpoint=str(cand.endpoint or ""),
                            key_selection=key_selection,
                        )
            except httpx.HTTPError as exc:
                record_key_failure(key_selection, retryable=True, status_code=None, redis=self.redis)
                last_status = None
                last_error = str(exc)
                await self.routing_state.increment_provider_failure(provider_id)
                continue
            except _RetryableCandidateError:
                continue

            record_key_success(key_selection, redis=self.redis)
            await self.routing_state.clear_provider_failure(provider_id)
            return resp

        message = f"All upstream providers failed for video model '{selection.logical_model.logical_id}'"
        details: list[str] = []
        if skipped_count:
            details.append(f"skipped={skipped_count} (in failure cooldown)")
        if last_status is not None:
            details.append(f"last_status={last_status}")
        if last_error:
            details.append(f"last_error={last_error}")
        detail_text = message if not details else f"{message}; " + ", ".join(details)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail_text)

    async def _call_openai_videos(
        self,
        *,
        http_client: httpx.AsyncClient,
        request: VideoGenerationRequest,
        selection,
        cfg,
        provider_id: str,
        model_id: str,
        endpoint: str,
        key_selection,
    ) -> VideoGenerationResponse:
        videos_path = _derive_openai_videos_path(getattr(cfg, "chat_completions_path", None))
        url = _apply_upstream_path_override(endpoint, videos_path)

        headers = build_upstream_headers(key_selection.key, cfg, call_style="openai", is_stream=False)
        headers.pop("Content-Type", None)
        headers["Accept"] = "application/json"

        vendor_extra = _get_vendor_extra(request, "openai")
        multipart_fields = _build_openai_videos_multipart_fields(request=request, model_id=model_id)
        if vendor_extra:
            # Best-effort: allow extra openai fields as simple scalar form fields.
            for k, v in vendor_extra.items():
                if not isinstance(k, str) or not k:
                    continue
                if k in multipart_fields:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    multipart_fields[k] = (None, str(v))

        if video_debug_logger.isEnabledFor(logging.DEBUG):
            safe = {k: v[1] for k, v in multipart_fields.items() if isinstance(v, tuple) and len(v) == 2}
            safe["prompt"] = "[omitted]" if safe.get("prompt") else ""
            video_debug_logger.debug(
                "openai_videos upstream payload provider=%s model_id=%s url=%s form=%s",
                provider_id,
                model_id,
                url,
                safe,
            )

        # OpenAI Video API 需要 multipart/form-data；即使不带文件也用 multipart 发送字段。
        resp = await http_client.post(url, headers=headers, files=multipart_fields)
        if resp.status_code >= 400:
            retryable = _is_retryable_upstream_status(provider_id, resp.status_code)
            record_key_failure(key_selection, retryable=retryable, status_code=resp.status_code, redis=self.redis)
            if retryable and resp.status_code in (500, 502, 503, 504, 429, 404, 405):
                await self.routing_state.increment_provider_failure(provider_id)
                raise _RetryableCandidateError()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream error {resp.status_code}: {resp.text}",
            )

        try:
            payload = resp.json()
        except ValueError:
            payload = {}

        video_id = _extract_openai_video_id(payload)
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Upstream returned no video id",
            )

        status_url = f"{url.rstrip('/')}/{video_id}"
        content_url = f"{url.rstrip('/')}/{video_id}/content"

        deadline = time.time() + 600.0
        while True:
            if time.time() >= deadline:
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="video generation timeout")

            st_resp = await http_client.get(status_url, headers=headers)
            if st_resp.status_code >= 400:
                retryable = _is_retryable_upstream_status(provider_id, st_resp.status_code)
                record_key_failure(key_selection, retryable=retryable, status_code=st_resp.status_code, redis=self.redis)
                if retryable and st_resp.status_code in (500, 502, 503, 504, 429):
                    await self.routing_state.increment_provider_failure(provider_id)
                    raise _RetryableCandidateError()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream status error {st_resp.status_code}: {st_resp.text}",
                )

            try:
                st_payload = st_resp.json()
            except ValueError:
                st_payload = {}

            st = _extract_openai_video_status(st_payload) or ""
            if st in {"queued", "in_progress", "processing"}:
                await anyio.sleep(2.0)
                continue
            if st == "failed":
                message = ""
                err = st_payload.get("error") if isinstance(st_payload, dict) else None
                if isinstance(err, dict) and isinstance(err.get("message"), str):
                    message = err["message"]
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=message or "video generation failed",
                )
            if st not in {"completed", "succeeded"}:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"unexpected upstream video status: {st}",
                )
            break

        download_resp = await http_client.get(content_url, headers=headers, params={"variant": "video"})
        if download_resp.status_code >= 400:
            retryable = _is_retryable_upstream_status(provider_id, download_resp.status_code)
            record_key_failure(key_selection, retryable=retryable, status_code=download_resp.status_code, redis=self.redis)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream download error {download_resp.status_code}: {download_resp.text}",
            )

        content_type = str(download_resp.headers.get("content-type") or "video/mp4")
        stored = await store_video_bytes(download_resp.content, content_type=content_type)
        signed = build_signed_video_url(stored.object_key)

        return VideoGenerationResponse(
            created=int(time.time()),
            data=[VideoObject(url=signed, object_key=stored.object_key)],
        )

    async def _call_google_veo_predict_long_running(
        self,
        *,
        http_client: httpx.AsyncClient,
        request: VideoGenerationRequest,
        selection,
        cfg,
        provider_id: str,
        model_id: str,
        base_url: str,
        key_selection,
    ) -> VideoGenerationResponse:
        model_path = str(model_id or "").strip()
        if not model_path:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="empty upstream model id")
        if not model_path.startswith("models/"):
            model_path = f"models/{model_path}"

        base = _google_v1beta_base(base_url)
        url = f"{base}/{model_path}:predictLongRunning"

        headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
        custom_headers = getattr(cfg, "custom_headers", None)
        if not isinstance(custom_headers, dict) or not any(
            str(k).strip().lower() == "x-goog-api-key" for k in custom_headers.keys()
        ):
            headers["x-goog-api-key"] = key_selection.key
        if isinstance(custom_headers, dict):
            headers.update(custom_headers)

        upstream_payload = _build_google_veo_predict_payload(request=request)

        # Handle input image for Veo
        image_url = getattr(request, "image_url", None)
        if isinstance(image_url, str) and image_url.strip():
            target_url = image_url.strip()
            # If it's a GCS URI, pass it directly
            if target_url.startswith("gs://"):
                upstream_payload["instances"][0]["image"] = {"uri": target_url}
            else:
                # Otherwise, fetch and encode
                try:
                    img_resp = await http_client.get(target_url, timeout=30.0)
                    if img_resp.status_code >= 400:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Failed to fetch input image: {img_resp.status_code}",
                        )
                    img_bytes = img_resp.content
                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                    mime_type = str(img_resp.headers.get("content-type") or "image/png")
                    upstream_payload["instances"][0]["image"] = {
                        "imageBytes": img_b64,
                        "mimeType": mime_type,
                    }
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.warning("failed to fetch video input image url=%s: %s", target_url, exc)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to fetch input image: {exc}",
                    )

        if video_debug_logger.isEnabledFor(logging.DEBUG):
            safe = dict(upstream_payload)
            inst = safe.get("instances")
            if isinstance(inst, list) and inst and isinstance(inst[0], dict):
                inst0 = dict(inst[0])
                inst0["prompt"] = "[omitted]"
                if "image" in inst0 and "imageBytes" in inst0["image"]:
                    # Don't log base64 image data
                    inst0["image"] = {**inst0["image"], "imageBytes": "[omitted]"}
                safe["instances"] = [inst0]
            video_debug_logger.debug(
                "google_veo upstream payload provider=%s model_id=%s url=%s body=%s",
                provider_id,
                model_id,
                url,
                safe,
            )

        start_resp = await http_client.post(url, headers=headers, json=upstream_payload)
        if start_resp.status_code >= 400:
            retryable = _is_retryable_upstream_status(provider_id, start_resp.status_code)
            record_key_failure(key_selection, retryable=retryable, status_code=start_resp.status_code, redis=self.redis)
            if retryable and start_resp.status_code in (500, 502, 503, 504, 429, 404, 405):
                await self.routing_state.increment_provider_failure(provider_id)
                raise _RetryableCandidateError()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream error {start_resp.status_code}: {start_resp.text}",
            )

        try:
            payload = start_resp.json()
        except ValueError:
            payload = {}

        op_name = _extract_google_operation_name(payload)
        if not op_name:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream returned no operation name")

        op_url = f"{base}/{op_name.lstrip('/')}"

        deadline = time.time() + 900.0
        while True:
            if time.time() >= deadline:
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="video generation timeout")
            st_resp = await http_client.get(op_url, headers=headers)
            if st_resp.status_code >= 400:
                retryable = _is_retryable_upstream_status(provider_id, st_resp.status_code)
                record_key_failure(key_selection, retryable=retryable, status_code=st_resp.status_code, redis=self.redis)
                if retryable and st_resp.status_code in (500, 502, 503, 504, 429):
                    await self.routing_state.increment_provider_failure(provider_id)
                    raise _RetryableCandidateError()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream status error {st_resp.status_code}: {st_resp.text}",
                )
            try:
                st_payload = st_resp.json()
            except ValueError:
                st_payload = {}
            if isinstance(st_payload, dict) and st_payload.get("done") is True:
                if isinstance(st_payload.get("error"), dict):
                    msg = st_payload["error"].get("message")
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(msg or "video generation failed"))
                uri = _extract_google_video_download_uri(st_payload)
                if not uri:
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream returned no video uri")
                download_resp = await http_client.get(uri, headers=headers)
                if download_resp.status_code >= 400:
                    retryable = _is_retryable_upstream_status(provider_id, download_resp.status_code)
                    record_key_failure(key_selection, retryable=retryable, status_code=download_resp.status_code, redis=self.redis)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Upstream download error {download_resp.status_code}: {download_resp.text}",
                    )
                content_type = str(download_resp.headers.get("content-type") or "video/mp4")
                stored = await store_video_bytes(download_resp.content, content_type=content_type)
                signed = build_signed_video_url(stored.object_key)
                return VideoGenerationResponse(
                    created=int(time.time()),
                    data=[VideoObject(url=signed, object_key=stored.object_key)],
                )

            await anyio.sleep(5.0)


__all__ = ["VideoAppService"]
