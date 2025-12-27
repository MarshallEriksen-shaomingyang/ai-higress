from __future__ import annotations

import base64
import hmac
import mimetypes
import time
import uuid
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Literal
from urllib.parse import quote

import anyio

from app.logging_config import logger
from app.settings import settings


class ImageStorageNotConfigured(RuntimeError):
    pass


class SignedUrlError(ValueError):
    pass


def _backend_kind() -> Literal["aliyun_oss", "s3"]:
    kind = str(settings.image_storage_provider or "aliyun_oss").strip().lower()
    if kind not in ("aliyun_oss", "s3"):
        raise ImageStorageNotConfigured(f"unsupported storage provider: {kind}")
    return kind  # type: ignore[return-value]


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


def _build_object_key(*, ext: str, kind: str | None = None) -> str:
    base_prefix = _normalize_prefix(settings.image_oss_prefix)
    prefix = base_prefix
    if kind:
        kind = _normalize_prefix(kind)
        prefix = f"{base_prefix}/{kind}" if base_prefix else kind
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


def _create_s3_client():
    if not _is_configured():
        raise ImageStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 S3/R2 存储")
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImageStorageNotConfigured(
            "缺少依赖 boto3，请安装后端依赖（backend/pyproject.toml）。"
        ) from exc

    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=str(settings.image_oss_endpoint).strip() or None,
        region_name=str(settings.image_oss_region or "").strip() or None,
        aws_access_key_id=str(settings.image_oss_access_key_id).strip() or None,
        aws_secret_access_key=str(settings.image_oss_access_key_secret).strip() or None,
        config=Config(signature_version="s3v4"),
    )


async def store_image_bytes(
    data: bytes, *, content_type: str | None = None, kind: str | None = None
) -> StoredImage:
    """
    将图片写入 OSS（私有桶），返回对象 key。
    """
    if not data:
        raise ValueError("empty image bytes")

    detected_type = content_type or _detect_content_type_from_bytes(data)
    ext = _guess_ext(detected_type)
    object_key = _build_object_key(ext=ext, kind=kind)

    kind_name = _backend_kind()

    def _put_oss() -> None:
        bucket = _create_oss_bucket()
        bucket.put_object(object_key, data, headers={"Content-Type": detected_type})

    def _put_s3() -> None:
        client = _create_s3_client()
        client.put_object(
            Bucket=str(settings.image_oss_bucket).strip(),
            Key=object_key,
            Body=data,
            ContentType=detected_type,
        )

    if kind_name == "aliyun_oss":
        await anyio.to_thread.run_sync(_put_oss)
    else:
        await anyio.to_thread.run_sync(_put_s3)

    return StoredImage(object_key=object_key, content_type=detected_type, size_bytes=len(data))


async def store_image_b64(
    b64_data: str, *, content_type: str | None = None, kind: str | None = None
) -> StoredImage:
    try:
        raw = base64.b64decode(b64_data)
    except Exception as exc:
        raise ValueError("invalid base64 image data") from exc
    return await store_image_bytes(raw, content_type=content_type, kind=kind)


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

    def _get_oss() -> tuple[bytes, str]:
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

    def _get_s3() -> tuple[bytes, str]:
        client = _create_s3_client()
        result = client.get_object(Bucket=str(settings.image_oss_bucket).strip(), Key=object_key)
        body_bytes: bytes = result["Body"].read()
        content_type = str(result.get("ContentType") or "")
        if not content_type:
            content_type = _detect_content_type_from_bytes(body_bytes)
        return body_bytes, content_type

    try:
        if _backend_kind() == "aliyun_oss":
            return await anyio.to_thread.run_sync(_get_oss)
        return await anyio.to_thread.run_sync(_get_s3)
    except Exception:
        logger.exception("Failed to load image from OSS/S3 (key=%s)", object_key)
        raise


async def presign_image_get_url(object_key: str, *, expires_seconds: int) -> str:
    """
    生成 OSS 预签名 GET URL，用于直下（不经由网关转发图片内容）。
    """
    if not _is_configured():
        raise ImageStorageNotConfigured("IMAGE_OSS_* 未配置，无法生成 OSS 预签名 URL")
    ttl = int(expires_seconds)
    if ttl <= 0:
        raise ValueError("expires_seconds must be positive")

    def _sign_oss() -> str:
        bucket = _create_oss_bucket()
        url = bucket.sign_url("GET", object_key, ttl)
        return str(url)

    def _sign_s3() -> str:
        client = _create_s3_client()
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": str(settings.image_oss_bucket).strip(), "Key": object_key},
            ExpiresIn=ttl,
        )

    try:
        if _backend_kind() == "aliyun_oss":
            return await anyio.to_thread.run_sync(_sign_oss)
        return await anyio.to_thread.run_sync(_sign_s3)
    except Exception:
        logger.exception("Failed to presign GET url (key=%s)", object_key)
        raise


@dataclass(frozen=True)
class PresignedUpload:
    object_key: str
    url: str
    headers: dict[str, str]
    expires_in: int


async def presign_object_put_url(
    *, content_type: str, kind: str | None = None, expires_seconds: int = 3600
) -> PresignedUpload:
    """
    生成直传（PUT）预签名 URL，便于客户端直接上传（用于未来视频/音频等大文件场景）。
    """
    if not _is_configured():
        raise ImageStorageNotConfigured("IMAGE_OSS_* 未配置，无法生成上传预签名 URL")
    ttl = int(expires_seconds)
    if ttl <= 0:
        raise ValueError("expires_seconds must be positive")

    ext = _guess_ext(content_type)
    object_key = _build_object_key(ext=ext, kind=kind)

    def _sign_oss() -> str:
        bucket = _create_oss_bucket()
        return bucket.sign_url(
            "PUT",
            object_key,
            ttl,
            headers={"Content-Type": content_type},
        )

    def _sign_s3() -> str:
        client = _create_s3_client()
        return client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": str(settings.image_oss_bucket).strip(),
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=ttl,
        )

    try:
        if _backend_kind() == "aliyun_oss":
            url = await anyio.to_thread.run_sync(_sign_oss)
        else:
            url = await anyio.to_thread.run_sync(_sign_s3)
    except Exception:
        logger.exception("Failed to presign PUT url (key=%s)", object_key)
        raise

    return PresignedUpload(
        object_key=object_key,
        url=str(url),
        headers={"Content-Type": content_type},
        expires_in=ttl,
    )


__all__ = [
    "ImageStorageNotConfigured",
    "SignedUrlError",
    "StoredImage",
    "PresignedUpload",
    "detect_image_content_type",
    "detect_image_content_type_b64",
    "build_signed_image_url",
    "load_image_bytes",
    "presign_image_get_url",
    "presign_object_put_url",
    "store_image_b64",
    "store_image_bytes",
    "verify_signed_image_request",
]
