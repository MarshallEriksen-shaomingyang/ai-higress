from __future__ import annotations

import base64
import hmac
import mimetypes
import os
import time
import uuid
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.parse import quote

import anyio

from app.logging_config import logger
from app.settings import settings


class ImageStorageNotConfigured(RuntimeError):
    pass


class SignedUrlError(ValueError):
    pass


def _is_configured() -> bool:
    required = (
        settings.image_oss_endpoint,
        settings.image_oss_bucket,
        settings.image_oss_access_key_id,
        settings.image_oss_access_key_secret,
    )
    return all(bool(str(v or "").strip()) for v in required)


@dataclass(frozen=True)
class StoredImage:
    object_key: str
    content_type: str
    size_bytes: int


def _normalize_prefix(prefix: str) -> str:
    value = str(prefix or "").strip().strip("/")
    return value


def _guess_ext(content_type: str | None) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type, strict=False)
        if ext:
            return ext.lstrip(".")
    return "png"


def _detect_content_type_from_bytes(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def detect_image_content_type(data: bytes) -> str:
    return _detect_content_type_from_bytes(data)


def detect_image_content_type_b64(b64_data: str) -> str:
    raw = base64.b64decode(b64_data)
    return _detect_content_type_from_bytes(raw)


def _build_object_key(*, ext: str) -> str:
    prefix = _normalize_prefix(settings.image_oss_prefix)
    uid = uuid.uuid4().hex
    date_part = time.strftime("%Y/%m/%d", time.gmtime())
    filename = f"{uid}.{ext}"
    if prefix:
        return f"{prefix}/{date_part}/{filename}"
    return f"{date_part}/{filename}"


def _create_oss_bucket():
    if not _is_configured():
        raise ImageStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 OSS 图片存储")

    try:
        import oss2  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImageStorageNotConfigured(
            "缺少依赖 oss2，请安装后端依赖（backend/pyproject.toml）。"
        ) from exc

    endpoint = str(settings.image_oss_endpoint).strip()
    bucket_name = str(settings.image_oss_bucket).strip()
    auth = oss2.Auth(
        str(settings.image_oss_access_key_id).strip(),
        str(settings.image_oss_access_key_secret).strip(),
    )
    return oss2.Bucket(auth, endpoint, bucket_name)


async def store_image_bytes(data: bytes, *, content_type: str | None = None) -> StoredImage:
    """
    将图片写入 OSS（私有桶），返回对象 key。
    """
    if not data:
        raise ValueError("empty image bytes")

    detected_type = content_type or _detect_content_type_from_bytes(data)
    ext = _guess_ext(detected_type)
    object_key = _build_object_key(ext=ext)

    def _put() -> None:
        bucket = _create_oss_bucket()
        bucket.put_object(object_key, data, headers={"Content-Type": detected_type})

    await anyio.to_thread.run_sync(_put)
    return StoredImage(object_key=object_key, content_type=detected_type, size_bytes=len(data))


async def store_image_b64(b64_data: str, *, content_type: str | None = None) -> StoredImage:
    try:
        raw = base64.b64decode(b64_data)
    except Exception as exc:
        raise ValueError("invalid base64 image data") from exc
    return await store_image_bytes(raw, content_type=content_type)


def _hmac_signature(object_key: str, expires_at: int) -> str:
    """
    生成短链签名（不依赖 OSS 签名）：HMAC-SHA256(secret_key, key\\nexpires) -> hex。
    """
    msg = f"{object_key}\n{int(expires_at)}".encode("utf-8")
    secret = str(settings.secret_key or "").encode("utf-8")
    return hmac.new(secret, msg, sha256).hexdigest()


def build_signed_image_url(object_key: str, *, base_url: str | None = None, ttl_seconds: int | None = None) -> str:
    """
    构造网关域名下的短链 URL：/media/images/{object_key}?expires=...&sig=...
    """
    api_base = (base_url or settings.gateway_api_base_url or "").rstrip("/")
    if not api_base:
        api_base = "http://localhost:8000"

    ttl = int(ttl_seconds or settings.image_signed_url_ttl_seconds or 3600)
    expires_at = int(time.time()) + max(1, ttl)
    sig = _hmac_signature(object_key, expires_at)

    # 保留 / 分隔，避免把层级 key 破坏；同时对特殊字符做转义。
    safe_key = quote(object_key, safe="/")
    return f"{api_base}/media/images/{safe_key}?expires={expires_at}&sig={sig}"


def verify_signed_image_request(object_key: str, *, expires: int, sig: str) -> None:
    now = int(time.time())
    if int(expires) <= now:
        raise SignedUrlError("signed url expired")

    expected = _hmac_signature(object_key, int(expires))
    if not hmac.compare_digest(str(sig or ""), expected):
        raise SignedUrlError("invalid signature")

    # Optional safety: enforce prefix to avoid using this endpoint as a generic OSS proxy.
    prefix = _normalize_prefix(settings.image_oss_prefix)
    if prefix and not str(object_key).startswith(prefix + "/"):
        raise SignedUrlError("invalid object key prefix")


async def load_image_bytes(object_key: str) -> tuple[bytes, str]:
    """
    从 OSS 拉取图片对象，返回 (bytes, content_type)。
    """
    if not _is_configured():
        raise ImageStorageNotConfigured("IMAGE_OSS_* 未配置，无法读取 OSS 图片")

    def _get() -> tuple[bytes, str]:
        bucket = _create_oss_bucket()
        result = bucket.get_object(object_key)
        content_type = str(getattr(result, "content_type", None) or "")
        if not content_type:
            headers: Any = getattr(result, "headers", None)
            if isinstance(headers, dict):
                content_type = str(headers.get("Content-Type") or headers.get("content-type") or "")
        body = result.read()
        if not content_type:
            content_type = _detect_content_type_from_bytes(body)
        return body, content_type

    try:
        return await anyio.to_thread.run_sync(_get)
    except Exception:
        logger.exception("Failed to load image from OSS (key=%s)", object_key)
        raise


__all__ = [
    "ImageStorageNotConfigured",
    "SignedUrlError",
    "StoredImage",
    "detect_image_content_type",
    "detect_image_content_type_b64",
    "build_signed_image_url",
    "load_image_bytes",
    "store_image_b64",
    "store_image_bytes",
    "verify_signed_image_request",
]
