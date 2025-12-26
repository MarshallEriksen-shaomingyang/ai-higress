from __future__ import annotations

import re
import time
from typing import Any

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

_OPENAI_IMAGE_MODEL_RE = re.compile(r"^(gpt-image|dall-e)", re.IGNORECASE)
_GOOGLE_IMAGE_MODEL_RE = re.compile(r"(gemini.*image|flash-image|^imagen)", re.IGNORECASE)


def _is_google_lane_model(model: str) -> bool:
    val = str(model or "").strip()
    if not val:
        return False
    if _OPENAI_IMAGE_MODEL_RE.search(val):
        return False
    return bool(_GOOGLE_IMAGE_MODEL_RE.search(val))


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

        if _is_google_lane_model(model):
            return await self._generate_with_google_lane(request, selection)
        return await self._generate_with_openai_lane(request, selection)

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
            upstream_payload["model"] = model_id

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
                retryable = _is_retryable_upstream_status(provider_id, resp.status_code)
                record_key_failure(
                    key_selection, retryable=retryable, status_code=resp.status_code, redis=self.redis
                )
                last_status = resp.status_code
                last_error = resp.text
                if retryable and resp.status_code in (500, 502, 503, 504, 429):
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
                retryable = _is_retryable_upstream_status(provider_id, resp.status_code)
                record_key_failure(
                    key_selection, retryable=retryable, status_code=resp.status_code, redis=self.redis
                )
                last_status = resp.status_code
                last_error = resp.text
                if retryable and resp.status_code in (500, 502, 503, 504, 429):
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
