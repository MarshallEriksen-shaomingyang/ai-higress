from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlsplit

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
from app.schemas.image import ImageGenerationRequest, ImageGenerationResponse, ImageObject
from app.services.chat_routing_service import _apply_upstream_path_override, _is_retryable_upstream_status
from app.services.credit_service import InsufficientCreditsError, ensure_account_usable
from app.services.image_storage_service import (
    ImageStorageNotConfigured,
    build_signed_image_url,
    detect_image_content_type_b64,
    store_image_b64,
)
from app.services.metrics_service import call_upstream_http_with_metrics
from app.services.user_provider_service import get_accessible_provider_ids
from app.schemas import ModelCapability

class _RetryableCandidateError(Exception):
    pass

_OPENAI_IMAGE_MODEL_RE = re.compile(r"^(gpt-image|dall-e)", re.IGNORECASE)
_GOOGLE_GEMINI_IMAGE_MODEL_RE = re.compile(r"(gemini.*image|flash-image|nano[- ]banana)", re.IGNORECASE)
_GOOGLE_IMAGEN_MODEL_RE = re.compile(r"^imagen", re.IGNORECASE)

image_debug_logger = logging.getLogger("apiproxy.image_debug")

_URL_RE = re.compile(r'(https?://[^\s)"\']+)')
_DATA_URL_RE = re.compile(
    r"(data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)"
)


def _extract_urls(text: str) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    return [m.group(1) for m in _URL_RE.finditer(text)]


def _extract_data_urls(text: str) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    return [m.group(1) for m in _DATA_URL_RE.finditer(text)]


def _image_object_from_url(text: str, *, fallback_prompt: str) -> ImageObject | None:
    if not isinstance(text, str) or not text:
        return None
    val = text.strip()
    if not val:
        return None
    if val.startswith("data:image/") and ";base64," in val:
        try:
            _, b64 = val.split(";base64,", 1)
        except ValueError:
            return None
        if b64:
            return ImageObject(b64_json=b64, revised_prompt=fallback_prompt)
        return None
    if val.startswith("http://") or val.startswith("https://"):
        return ImageObject(url=val, revised_prompt=fallback_prompt)
    return None


def _extract_images_from_message_obj(message: dict[str, Any], *, fallback_prompt: str) -> list[ImageObject]:
    images: list[ImageObject] = []

    def _consume_url(value: Any) -> None:
        obj = _image_object_from_url(str(value), fallback_prompt=fallback_prompt) if value is not None else None
        if obj is not None:
            images.append(obj)

    for key in ("image_url", "url", "image"):
        val = message.get(key)
        if isinstance(val, dict) and isinstance(val.get("url"), str):
            _consume_url(val.get("url"))
        elif isinstance(val, str):
            _consume_url(val)

    imgs = message.get("images")
    if isinstance(imgs, list):
        for item in imgs:
            if isinstance(item, dict):
                if isinstance(item.get("url"), str):
                    _consume_url(item.get("url"))
                if isinstance(item.get("b64_json"), str):
                    images.append(ImageObject(b64_json=item["b64_json"], revised_prompt=fallback_prompt))
                if isinstance(item.get("data"), str):
                    # Some upstreams use `data:` for base64.
                    obj = _image_object_from_url(item["data"], fallback_prompt=fallback_prompt)
                    if obj is not None:
                        images.append(obj)
            elif isinstance(item, str):
                _consume_url(item)

    return images


def _extract_images_from_chat_completion_payload(payload: Any, *, fallback_prompt: str) -> list[ImageObject]:
    """
    Some upstreams return image generation results as Chat Completions response.

    Try to extract image URLs or base64 blobs from a chat-like payload and
    map them into ImageObject list.
    """
    if not isinstance(payload, dict):
        return []
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return []

    images: list[ImageObject] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else None
        if message is None:
            continue
        images.extend(_extract_images_from_message_obj(message, fallback_prompt=fallback_prompt))
        if images:
            continue
        content = message.get("content")

        # Newer style: content as list of parts (e.g., image_url objects).
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                image_url = part.get("image_url")
                if isinstance(image_url, dict) and isinstance(image_url.get("url"), str) and image_url["url"]:
                    obj = _image_object_from_url(image_url["url"], fallback_prompt=fallback_prompt)
                    if obj is not None:
                        images.append(obj)
                    continue
                if part.get("type") == "image_url" and isinstance(part.get("url"), str) and part["url"]:
                    obj = _image_object_from_url(part["url"], fallback_prompt=fallback_prompt)
                    if obj is not None:
                        images.append(obj)
                    continue
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    for u in _extract_urls(part["text"]):
                        obj = _image_object_from_url(u, fallback_prompt=fallback_prompt)
                        if obj is not None:
                            images.append(obj)
                    for u in _extract_data_urls(part["text"]):
                        obj = _image_object_from_url(u, fallback_prompt=fallback_prompt)
                        if obj is not None:
                            images.append(obj)
            continue

        # Classic style: content as string (may include plain URL, markdown, or JSON).
        if isinstance(content, str) and content.strip():
            raw = content.strip()
            # Try JSON first (some upstreams embed images result as JSON string).
            if raw.startswith("{") or raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("url"), str) and parsed["url"]:
                        images.append(ImageObject(url=parsed["url"], revised_prompt=fallback_prompt))
                        continue
                    if isinstance(parsed.get("b64_json"), str) and parsed["b64_json"]:
                        images.append(ImageObject(b64_json=parsed["b64_json"], revised_prompt=fallback_prompt))
                        continue
                    data = parsed.get("data")
                    if isinstance(data, list):
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            url = item.get("url")
                            b64_json = item.get("b64_json")
                            if isinstance(url, str) and url:
                                images.append(ImageObject(url=url, revised_prompt=fallback_prompt))
                            elif isinstance(b64_json, str) and b64_json:
                                images.append(ImageObject(b64_json=b64_json, revised_prompt=fallback_prompt))
                        if images:
                            continue

            for u in _extract_urls(raw):
                obj = _image_object_from_url(u, fallback_prompt=fallback_prompt)
                if obj is not None:
                    images.append(obj)
            for u in _extract_data_urls(raw):
                obj = _image_object_from_url(u, fallback_prompt=fallback_prompt)
                if obj is not None:
                    images.append(obj)
            continue

    return images


def _redact_image_upstream_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Redact sensitive user content from upstream request payloads before logging.

    - prompt -> "[omitted]"
    - messages[*].content -> "[omitted]"
    - contents[*].parts[*].text (Gemini) -> "[omitted]"
    """
    try:
        redacted: dict[str, Any] = dict(payload)
    except Exception:
        return {"_redacted": True}

    if "prompt" in redacted:
        redacted["prompt"] = "[omitted]"

    msgs = redacted.get("messages")
    if isinstance(msgs, list):
        masked_msgs: list[dict[str, Any]] = []
        for msg in msgs:
            if not isinstance(msg, dict):
                continue
            copied = dict(msg)
            if "content" in copied:
                copied["content"] = "[omitted]"
            masked_msgs.append(copied)
        redacted["messages"] = masked_msgs

    contents = redacted.get("contents")
    if isinstance(contents, list):
        masked_contents: list[dict[str, Any]] = []
        for item in contents:
            if not isinstance(item, dict):
                continue
            copied_item = dict(item)
            parts = copied_item.get("parts")
            if isinstance(parts, list):
                masked_parts: list[dict[str, Any]] = []
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    copied_part = dict(part)
                    if "text" in copied_part:
                        copied_part["text"] = "[omitted]"
                    masked_parts.append(copied_part)
                copied_item["parts"] = masked_parts
            masked_contents.append(copied_item)
        redacted["contents"] = masked_contents

    return redacted


def _is_google_lane_model(model: str) -> bool:
    val = str(model or "").strip()
    if not val:
        return False
    if _OPENAI_IMAGE_MODEL_RE.search(val):
        return False
    return bool(_GOOGLE_GEMINI_IMAGE_MODEL_RE.search(val) or _GOOGLE_IMAGEN_MODEL_RE.search(val))


def _is_google_imagen_model(model: str) -> bool:
    val = str(model or "").strip()
    if not val:
        return False
    if _OPENAI_IMAGE_MODEL_RE.search(val):
        return False
    return bool(_GOOGLE_IMAGEN_MODEL_RE.search(val))


def _is_google_native_provider_base_url(base_url: str) -> bool:
    """
    判断某个 provider 是否按 Gemini API 的原生 REST 地址配置：
    https://generativelanguage.googleapis.com
    """
    raw = str(base_url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlsplit(raw)
    except Exception:
        return False
    return str(parsed.netloc or "").lower() == "generativelanguage.googleapis.com"


def _derive_openai_images_path(provider_chat_path: str | None) -> str:
    """
    尽量从 provider 的 chat_completions_path 推导对应的 images/generations 路径，
    以兼容 base_url 是否自带 /v1 的两种配置方式。
    """
    raw = str(provider_chat_path or "/v1/chat/completions").strip() or "/v1/chat/completions"
    lowered = raw.lower()
    if "chat/completions" in lowered:
        # Keep leading '/v1' if present.
        prefix = raw[: lowered.rfind("chat/completions")]
        return f"{prefix}images/generations".replace("//", "/")
    return "/v1/images/generations"


def _has_header(headers: dict[str, str] | None, name: str) -> bool:
    if not headers:
        return False
    target = name.strip().lower()
    for key in headers.keys():
        if str(key).strip().lower() == target:
            return True
    return False


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge override into base and return base (mutated).
    """
    for key, value in override.items():
        if (
            key in base
            and isinstance(base.get(key), dict)
            and isinstance(value, dict)
        ):
            _deep_merge_dict(base[key], value)  # type: ignore[index]
            continue
        base[key] = value
    return base


def _get_vendor_extra(request: ImageGenerationRequest, vendor: str) -> dict[str, Any] | None:
    extra = getattr(request, "extra_body", None)
    if not isinstance(extra, dict):
        return None
    payload = extra.get(vendor)
    if not isinstance(payload, dict):
        return None
    return payload


def _map_openai_size_to_google_image_config(size: str | None) -> dict[str, str] | None:
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

    # Google discovery: aspectRatio supports: 1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9
    ratio_map: dict[tuple[int, int], str] = {
        (1, 1): "1:1",
        (2, 3): "2:3",
        (3, 2): "3:2",
        (3, 4): "3:4",
        (4, 3): "4:3",
        (9, 16): "9:16",
        (16, 9): "16:9",
        (21, 9): "21:9",
    }
    # Reduce ratio.
    def _gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a

    g = _gcd(w, h)
    rw, rh = w // g, h // g
    aspect_ratio = ratio_map.get((rw, rh))

    # Google discovery: imageSize supports: 1K, 2K, 4K
    max_dim = max(w, h)
    if max_dim <= 1024:
        image_size = "1K"
    elif max_dim <= 2048:
        image_size = "2K"
    else:
        image_size = "4K"

    out: dict[str, str] = {"imageSize": image_size}
    if aspect_ratio:
        out["aspectRatio"] = aspect_ratio
    return out


def _map_openai_size_to_google_imagen_parameters(size: str | None) -> dict[str, str] | None:
    """
    对照官方 Imagen REST 文档（/v1beta/models/{model}:predict）：
    - aspectRatio: 1:1, 3:4, 4:3, 9:16, 16:9
    - imageSize: 1K, 2K
    """
    cfg = _map_openai_size_to_google_image_config(size)
    if not cfg:
        return None

    out: dict[str, str] = {}
    ar = cfg.get("aspectRatio")
    if ar in {"1:1", "3:4", "4:3", "9:16", "16:9"}:
        out["aspectRatio"] = ar

    img_size = cfg.get("imageSize")
    if img_size == "2K" or img_size == "4K":
        out["imageSize"] = "2K"
    elif img_size == "1K":
        out["imageSize"] = "1K"

    return out or None


class ImageAppService:
    """
    文生图入口（OpenAI 兼容）：固定对外为 OpenAI 的 `/v1/images/generations` 协议，
    内部根据 model 走两条上游链路：
    - OpenAI lane：调用各 OpenAI-compatible Provider 的 images/generations
    - Google lane：调用 Gemini Developer API 的 generateContent (v1beta)
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
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

    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
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

        # 选路仍使用现有 ProviderSelector（逻辑模型/动态模型发现/失败冷却/调度策略一致）。
        selection = await self.provider_selector.select(
            requested_model=model,
            lookup_model_id=model,
            api_style="openai",
            effective_provider_ids=effective_provider_ids,
            session_id=None,
            user_id=self.api_key.user_id,
            is_superuser=bool(self.api_key.is_superuser),
        )

        caps = set(getattr(selection.logical_model, "capabilities", None) or [])
        if ModelCapability.IMAGE_GENERATION not in caps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "该模型不支持文生图（image_generation）能力"},
            )

        return await self._generate_with_mixed_lanes(request, selection)

    async def _generate_with_mixed_lanes(
        self,
        request: ImageGenerationRequest,
        selection,
    ) -> ImageGenerationResponse:
        """
        逐个候选 provider 尝试，按 provider 配置决定调用协议，避免“按 model 正则”导致的抽象泄漏：

        - Provider.base_url = https://generativelanguage.googleapis.com：
          - imagen-* -> :predict（Imagen 专用）
          - 其他 -> :generateContent（Gemini 多模态输出 IMAGE）
        - 其他 base_url：按 OpenAI Images API 走 /v1/images/generations
        """
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
                if _is_google_native_provider_base_url(base_url):
                    if _is_google_imagen_model(str(model_id or "")):
                        resp = await self._call_google_imagen_predict(
                            request=request,
                            selection=selection,
                            cfg=cfg,
                            provider_id=provider_id,
                            model_id=model_id,
                            base_url=base_url,
                            key_selection=key_selection,
                        )
                    else:
                        resp = await self._call_google_generate_content(
                            request=request,
                            selection=selection,
                            cfg=cfg,
                            provider_id=provider_id,
                            model_id=model_id,
                            base_url=base_url,
                            key_selection=key_selection,
                        )
                else:
                    resp = await self._call_openai_images_generations(
                        request=request,
                        selection=selection,
                        cfg=cfg,
                        provider_id=provider_id,
                        model_id=model_id,
                        endpoint=cand.endpoint,
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

        message = f"All upstream providers failed for image model '{selection.logical_model.logical_id}'"
        details: list[str] = []
        if skipped_count:
            details.append(f"skipped={skipped_count} (in failure cooldown)")
        if last_status is not None:
            details.append(f"last_status={last_status}")
        if last_error:
            details.append(f"last_error={last_error}")
        detail_text = message if not details else f"{message}; " + ", ".join(details)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail_text)

    async def _call_openai_images_generations(
        self,
        *,
        request: ImageGenerationRequest,
        selection,
        cfg,
        provider_id: str,
        model_id: str,
        endpoint: str,
        key_selection,
    ) -> ImageGenerationResponse:
        images_path = getattr(cfg, "images_generations_path", None) or _derive_openai_images_path(
            getattr(cfg, "chat_completions_path", None)
        )
        url = _apply_upstream_path_override(endpoint, images_path)
        headers = build_upstream_headers(key_selection.key, cfg, call_style="openai", is_stream=False)

        # Some non-standard upstreams expose image generation via Chat Completions endpoint,
        # requiring OpenAI chat payload shape (messages) instead of Images API (prompt).
        images_path_lower = str(images_path or "").lower()
        is_chat_completions_images = "chat/completions" in images_path_lower
        if is_chat_completions_images:
            upstream_payload: dict[str, Any] = {
                "model": model_id,
                "messages": [{"role": "user", "content": request.prompt}],
                "n": int(getattr(request, "n", 1) or 1),
            }
        else:
            upstream_payload = request.model_dump(exclude_none=True)
        vendor_extra = _get_vendor_extra(request, "openai")
        if vendor_extra:
            _deep_merge_dict(upstream_payload, vendor_extra)
        gateway_extra = _get_vendor_extra(request, "gateway") or {}
        upstream_payload["model"] = model_id
        upstream_payload.pop("extra_body", None)
        # 网关当前不支持上游 Images SSE；防止用户误传导致 resp.json 失败。
        if not is_chat_completions_images:
            upstream_payload.pop("stream", None)
            upstream_payload.pop("partial_images", None)
        if bool(gateway_extra.get("omit_response_format")):
            upstream_payload.pop("response_format", None)

        if image_debug_logger.isEnabledFor(logging.DEBUG):
            safe_payload = _redact_image_upstream_payload(upstream_payload)
            image_debug_logger.debug(
                "openai_images upstream payload provider=%s model_id=%s url=%s body=%s",
                provider_id,
                model_id,
                url,
                safe_payload,
            )

        resp = await call_upstream_http_with_metrics(
            client=self.client,
            url=url,
            headers=headers,
            json_body=upstream_payload,
            db=self.db,
            provider_id=provider_id,
            logical_model=selection.logical_model.logical_id,
            user_id=self.api_key.user_id,
            api_key_id=self.api_key.id,
        )

        if resp.status_code >= 400:
            mismatch = resp.status_code in (404, 405)
            retryable = True if mismatch else _is_retryable_upstream_status(provider_id, resp.status_code)
            record_key_failure(key_selection, retryable=retryable, status_code=resp.status_code, redis=self.redis)
            # 仅在错误时输出上游 payload（避免丢调试信息）；屏蔽 prompt 以减少隐私暴露。
            safe_payload = dict(upstream_payload)
            safe_payload = _redact_image_upstream_payload(safe_payload)
            logger.warning(
                "openai_images upstream error: status=%s provider=%s model_id=%s url=%s payload=%s",
                resp.status_code,
                provider_id,
                model_id,
                url,
                safe_payload,
            )
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
            payload = {"raw": resp.text}
        if is_chat_completions_images:
            if isinstance(payload, dict) and "data" in payload:
                parsed = ImageGenerationResponse.model_validate(payload)
            else:
                images = _extract_images_from_chat_completion_payload(
                    payload, fallback_prompt=request.prompt
                )
                if not images:
                    keys = []
                    if isinstance(payload, dict):
                        keys = sorted([str(k) for k in payload.keys()])[:30]
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=(
                            "Upstream returned chat completion response but no image URL/b64 could be extracted"
                            + (f" (keys={keys})" if keys else "")
                        ),
                    )
                parsed = ImageGenerationResponse(created=int(time.time()), data=images)
        else:
            parsed = ImageGenerationResponse.model_validate(payload)
        if request.response_format == "url":
            parsed = await self._ensure_signed_urls_for_response(parsed)
        return parsed

    async def _call_google_generate_content(
        self,
        *,
        request: ImageGenerationRequest,
        selection,
        cfg,
        provider_id: str,
        model_id: str,
        base_url: str,
        key_selection,
    ) -> ImageGenerationResponse:
        model_path = str(model_id or "").strip()
        if not model_path:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="empty upstream model id")
        if not model_path.startswith("models/"):
            model_path = f"models/{model_path}"
        url = f"{base_url}/v1beta/{model_path}:generateContent"

        headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
        if not _has_header(getattr(cfg, "custom_headers", None), "x-goog-api-key"):
            headers["x-goog-api-key"] = key_selection.key
        if getattr(cfg, "custom_headers", None):
            headers.update(getattr(cfg, "custom_headers"))

        generation_config: dict[str, Any] = {
            "candidateCount": int(request.n),
            "responseModalities": ["TEXT", "IMAGE"],
        }
        image_cfg = _map_openai_size_to_google_image_config(getattr(request, "size", None))
        if image_cfg:
            generation_config["imageConfig"] = image_cfg

        upstream_payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": generation_config,
        }
        vendor_extra = _get_vendor_extra(request, "google")
        if vendor_extra:
            _deep_merge_dict(upstream_payload, vendor_extra)

        if image_debug_logger.isEnabledFor(logging.DEBUG):
            safe_payload = _redact_image_upstream_payload(upstream_payload)
            image_debug_logger.debug(
                "google_generateContent upstream payload provider=%s model_id=%s url=%s body=%s",
                provider_id,
                model_id,
                url,
                safe_payload,
            )

        resp = await call_upstream_http_with_metrics(
            client=self.client,
            url=url,
            headers=headers,
            json_body=upstream_payload,
            db=self.db,
            provider_id=provider_id,
            logical_model=selection.logical_model.logical_id,
            user_id=self.api_key.user_id,
            api_key_id=self.api_key.id,
        )

        if resp.status_code >= 400:
            mismatch = resp.status_code in (404, 405)
            retryable = True if mismatch else _is_retryable_upstream_status(provider_id, resp.status_code)
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

        images: list[ImageObject] = []
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                parts = candidate.get("content", {}).get("parts", [])
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    inline = part.get("inlineData") or part.get("inline_data")
                    if not isinstance(inline, dict):
                        continue
                    b64_data = inline.get("data")
                    if not isinstance(b64_data, str) or not b64_data:
                        continue
                    images.append(ImageObject(b64_json=b64_data, revised_prompt=request.prompt))

        if not images:
            logger.warning(
                "google_image: empty inlineData (provider=%s model=%s response=%s)",
                provider_id,
                model_id,
                str(payload)[:500],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google image generation returned no images",
            )

        response = ImageGenerationResponse(created=int(time.time()), data=images)
        if request.response_format == "url":
            response = await self._ensure_signed_urls_for_response(response)
        return response

    async def _call_google_imagen_predict(
        self,
        *,
        request: ImageGenerationRequest,
        selection,
        cfg,
        provider_id: str,
        model_id: str,
        base_url: str,
        key_selection,
    ) -> ImageGenerationResponse:
        model_path = str(model_id or "").strip()
        if not model_path:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="empty upstream model id")
        if not model_path.startswith("models/"):
            model_path = f"models/{model_path}"
        url = f"{base_url}/v1beta/{model_path}:predict"

        headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
        if not _has_header(getattr(cfg, "custom_headers", None), "x-goog-api-key"):
            headers["x-goog-api-key"] = key_selection.key
        if getattr(cfg, "custom_headers", None):
            headers.update(getattr(cfg, "custom_headers"))

        parameters: dict[str, Any] = {"sampleCount": int(request.n)}
        mapped = _map_openai_size_to_google_imagen_parameters(getattr(request, "size", None))
        if mapped:
            parameters.update(mapped)

        upstream_payload: dict[str, Any] = {
            "instances": [{"prompt": request.prompt}],
            "parameters": parameters,
        }
        vendor_extra = _get_vendor_extra(request, "google")
        if vendor_extra:
            _deep_merge_dict(upstream_payload, vendor_extra)

        if image_debug_logger.isEnabledFor(logging.DEBUG):
            safe_payload = _redact_image_upstream_payload(upstream_payload)
            image_debug_logger.debug(
                "google_imagen_predict upstream payload provider=%s model_id=%s url=%s body=%s",
                provider_id,
                model_id,
                url,
                safe_payload,
            )

        resp = await call_upstream_http_with_metrics(
            client=self.client,
            url=url,
            headers=headers,
            json_body=upstream_payload,
            db=self.db,
            provider_id=provider_id,
            logical_model=selection.logical_model.logical_id,
            user_id=self.api_key.user_id,
            api_key_id=self.api_key.id,
        )

        if resp.status_code >= 400:
            mismatch = resp.status_code in (404, 405)
            retryable = True if mismatch else _is_retryable_upstream_status(provider_id, resp.status_code)
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

        predictions = payload.get("predictions") if isinstance(payload, dict) else None
        images: list[ImageObject] = []
        if isinstance(predictions, list):
            for pred in predictions:
                if not isinstance(pred, dict):
                    continue
                b64_data = pred.get("bytesBase64Encoded")
                if not isinstance(b64_data, str) or not b64_data:
                    continue
                revised = pred.get("prompt")
                revised_prompt = revised if isinstance(revised, str) and revised.strip() else request.prompt
                images.append(ImageObject(b64_json=b64_data, revised_prompt=revised_prompt))

        if not images:
            logger.warning(
                "google_imagen: empty predictions (provider=%s model=%s response=%s)",
                provider_id,
                model_id,
                str(payload)[:500],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google Imagen returned no images",
            )

        response = ImageGenerationResponse(created=int(time.time()), data=images)
        if request.response_format == "url":
            response = await self._ensure_signed_urls_for_response(response)
        return response

    async def _generate_with_openai_lane(
        self,
        request: ImageGenerationRequest,
        selection,
    ) -> ImageGenerationResponse:
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

            try:
                key_selection = await acquire_provider_key(cfg, self.redis)
            except NoAvailableProviderKey as exc:
                last_status = status.HTTP_503_SERVICE_UNAVAILABLE
                last_error = str(exc)
                continue

            images_path = getattr(cfg, "images_generations_path", None) or _derive_openai_images_path(
                getattr(cfg, "chat_completions_path", None)
            )
            url = _apply_upstream_path_override(cand.endpoint, images_path)
            headers = build_upstream_headers(
                key_selection.key, cfg, call_style="openai", is_stream=False
            )

            upstream_payload: dict[str, Any] = request.model_dump(exclude_none=True)
            vendor_extra = _get_vendor_extra(request, "openai")
            if vendor_extra:
                _deep_merge_dict(upstream_payload, vendor_extra)
            upstream_payload["model"] = model_id
            upstream_payload.pop("extra_body", None)

            try:
                resp = await call_upstream_http_with_metrics(
                    client=self.client,
                    url=url,
                    headers=headers,
                    json_body=upstream_payload,
                    db=self.db,
                    provider_id=provider_id,
                    logical_model=selection.logical_model.logical_id,
                    user_id=self.api_key.user_id,
                    api_key_id=self.api_key.id,
                )
            except httpx.HTTPError as exc:
                record_key_failure(key_selection, retryable=True, status_code=None, redis=self.redis)
                last_status = None
                last_error = str(exc)
                await self.routing_state.increment_provider_failure(provider_id)
                continue

            if resp.status_code >= 400:
                mismatch = resp.status_code in (404, 405)
                retryable = True if mismatch else _is_retryable_upstream_status(provider_id, resp.status_code)
                record_key_failure(
                    key_selection, retryable=retryable, status_code=resp.status_code, redis=self.redis
                )
                last_status = resp.status_code
                last_error = resp.text
                if retryable and resp.status_code in (500, 502, 503, 504, 429, 404, 405):
                    await self.routing_state.increment_provider_failure(provider_id)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream error {resp.status_code}: {resp.text}",
                )

            record_key_success(key_selection, redis=self.redis)
            await self.routing_state.clear_provider_failure(provider_id)

            try:
                payload = resp.json()
            except ValueError:
                payload = {"raw": resp.text}

            # 允许 OpenAI 上游返回额外字段（background/usage 等），response_model 会做收敛。
            parsed = ImageGenerationResponse.model_validate(payload)

            if request.response_format == "url":
                parsed = await self._ensure_signed_urls_for_response(parsed)
            return parsed

        message = f"All upstream providers failed for image model '{selection.logical_model.logical_id}'"
        details: list[str] = []
        if skipped_count:
            details.append(f"skipped={skipped_count} (in failure cooldown)")
        if last_status is not None:
            details.append(f"last_status={last_status}")
        if last_error:
            details.append(f"last_error={last_error}")
        detail_text = message if not details else f"{message}; " + ", ".join(details)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail_text)

    async def _generate_with_google_lane(
        self,
        request: ImageGenerationRequest,
        selection,
    ) -> ImageGenerationResponse:
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

            model_path = str(model_id or "").strip()
            if not model_path:
                last_status = status.HTTP_502_BAD_GATEWAY
                last_error = "empty upstream model id"
                continue
            if not model_path.startswith("models/"):
                model_path = f"models/{model_path}"
            url = f"{base_url}/v1beta/{model_path}:generateContent"

            headers: dict[str, str] = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if not _has_header(getattr(cfg, "custom_headers", None), "x-goog-api-key"):
                headers["x-goog-api-key"] = key_selection.key
            if getattr(cfg, "custom_headers", None):
                headers.update(getattr(cfg, "custom_headers"))

            generation_config: dict[str, Any] = {
                "candidateCount": int(request.n),
                "responseModalities": ["TEXT", "IMAGE"],
            }
            image_cfg = _map_openai_size_to_google_image_config(getattr(request, "size", None))
            if image_cfg:
                generation_config["imageConfig"] = image_cfg

            upstream_payload: dict[str, Any] = {
                "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
                "generationConfig": generation_config,
            }
            vendor_extra = _get_vendor_extra(request, "google")
            if vendor_extra:
                _deep_merge_dict(upstream_payload, vendor_extra)

            try:
                resp = await call_upstream_http_with_metrics(
                    client=self.client,
                    url=url,
                    headers=headers,
                    json_body=upstream_payload,
                    db=self.db,
                    provider_id=provider_id,
                    logical_model=selection.logical_model.logical_id,
                    user_id=self.api_key.user_id,
                    api_key_id=self.api_key.id,
                )
            except httpx.HTTPError as exc:
                record_key_failure(key_selection, retryable=True, status_code=None, redis=self.redis)
                last_status = None
                last_error = str(exc)
                await self.routing_state.increment_provider_failure(provider_id)
                continue

            if resp.status_code >= 400:
                mismatch = resp.status_code in (404, 405)
                retryable = True if mismatch else _is_retryable_upstream_status(provider_id, resp.status_code)
                record_key_failure(
                    key_selection, retryable=retryable, status_code=resp.status_code, redis=self.redis
                )
                last_status = resp.status_code
                last_error = resp.text
                if retryable and resp.status_code in (500, 502, 503, 504, 429, 404, 405):
                    await self.routing_state.increment_provider_failure(provider_id)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream error {resp.status_code}: {resp.text}",
                )

            record_key_success(key_selection, redis=self.redis)
            await self.routing_state.clear_provider_failure(provider_id)

            try:
                payload = resp.json()
            except ValueError:
                payload = {}

            images: list[ImageObject] = []
            candidates = payload.get("candidates") if isinstance(payload, dict) else None
            if isinstance(candidates, list):
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    parts = candidate.get("content", {}).get("parts", [])
                    if not isinstance(parts, list):
                        continue
                    for part in parts:
                        if not isinstance(part, dict):
                            continue
                        inline = part.get("inlineData") or part.get("inline_data")
                        if not isinstance(inline, dict):
                            continue
                        b64_data = inline.get("data")
                        mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                        if not isinstance(b64_data, str) or not b64_data:
                            continue
                        images.append(
                            ImageObject(b64_json=b64_data, revised_prompt=request.prompt)
                        )

            if not images:
                logger.warning(
                    "google_image: empty inlineData (provider=%s model=%s response=%s)",
                    provider_id,
                    model_id,
                    str(payload)[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Google image generation returned no images",
                )

            response = ImageGenerationResponse(created=int(time.time()), data=images)
            if request.response_format == "url":
                response = await self._ensure_signed_urls_for_response(response)
            return response

        message = f"All upstream providers failed for image model '{selection.logical_model.logical_id}'"
        details: list[str] = []
        if skipped_count:
            details.append(f"skipped={skipped_count} (in failure cooldown)")
        if last_status is not None:
            details.append(f"last_status={last_status}")
        if last_error:
            details.append(f"last_error={last_error}")
        detail_text = message if not details else f"{message}; " + ", ".join(details)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail_text)

    async def _ensure_signed_urls_for_response(
        self,
        response: ImageGenerationResponse,
    ) -> ImageGenerationResponse:
        """
        当调用方请求 response_format=url 时，将 b64_json 上传到 OSS，并返回网关签名短链 URL。

        - 未配置 OSS 时，保持原响应（通常会返回 b64_json），由前端自行处理。
        """
        if not response.data:
            return response

        updated: list[ImageObject] = []
        for item in response.data:
            if item.url:
                updated.append(item)
                continue
            if not item.b64_json:
                updated.append(item)
                continue
            try:
                stored = await store_image_b64(item.b64_json)
                url = build_signed_image_url(stored.object_key)
                updated.append(ImageObject(url=url, revised_prompt=item.revised_prompt))
                continue
            except ImageStorageNotConfigured:
                # OSS 未配置：退化为 data URL，尽量保持 response_format=url 语义
                try:
                    mime = detect_image_content_type_b64(item.b64_json)
                except Exception:
                    mime = "image/png"
                updated.append(
                    ImageObject(
                        url=f"data:{mime};base64,{item.b64_json}",
                        revised_prompt=item.revised_prompt,
                    )
                )
                continue
            except Exception:
                # OSS 上传失败：保持 b64_json，不阻断主流程（避免偶发存储故障让生成完全失败）
                updated.append(item)
                continue

        return response.model_copy(update={"data": updated})
