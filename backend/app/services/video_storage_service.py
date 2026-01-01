from __future__ import annotations

import hmac
import mimetypes
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import anyio

from app.logging_config import logger
from app.settings import settings


class VideoStorageNotConfigured(RuntimeError):
    pass


class SignedVideoUrlError(RuntimeError):
    pass


_VIDEO_OBJECT_KIND = "videos"


def _normalize_prefix(value: str | None) -> str:
    raw = str(value or "").strip().strip("/")
    raw = raw.replace("\\", "/")
    parts = [p for p in raw.split("/") if p]
    return "/".join(parts)


def _video_object_prefix() -> str:
    base = _normalize_prefix(getattr(settings, "image_oss_prefix", None))
    kind = _normalize_prefix(_VIDEO_OBJECT_KIND)
    if base and kind:
        return f"{base}/{kind}"
    return base or kind


def _build_object_key(*, ext: str) -> str:
    prefix = _video_object_prefix()
    uid = uuid.uuid4().hex
    date_part = time.strftime("%Y/%m/%d", time.gmtime())
    filename = f"{uid}.{ext}"
    if prefix:
        return f"{prefix}/{date_part}/{filename}"
    return f"{date_part}/{filename}"


def _local_base_dir() -> Path:
    base = Path(str(getattr(settings, "image_local_dir", "") or "")).expanduser()
    return base.resolve()


def _local_path_for_object_key(object_key: str) -> Path:
    raw = str(object_key or "").lstrip("/").replace("\\", "/")
    parts = [p for p in raw.split("/") if p]
    if not parts:
        raise ValueError("empty object key")
    if any(p in {".", ".."} for p in parts):
        raise ValueError("invalid object key path")

    base_dir = _local_base_dir()
    target = base_dir.joinpath(*parts).resolve()
    if not target.is_relative_to(base_dir):
        raise ValueError("invalid object key path")
    return target


def _oss_backend_kind() -> Literal["aliyun_oss", "s3"]:
    kind = str(
        getattr(settings, "oss_provider", None)
        or getattr(settings, "image_storage_provider", None)
        or "aliyun_oss"
    ).strip().lower()
    if kind not in ("aliyun_oss", "s3"):
        raise VideoStorageNotConfigured(f"unsupported storage provider: {kind}")
    return kind  # type: ignore[return-value]


def _resolve_bucket() -> str:
    return str(
        getattr(settings, "image_oss_bucket", None)
        or getattr(settings, "oss_private_bucket", None)
        or getattr(settings, "oss_public_bucket", None)
        or ""
    ).strip()


def _resolve_endpoint() -> str:
    return str(getattr(settings, "image_oss_endpoint", None) or getattr(settings, "oss_endpoint", None) or "").strip()


def _resolve_region() -> str:
    return str(getattr(settings, "image_oss_region", None) or getattr(settings, "oss_region", None) or "").strip()


def _resolve_access_key_id() -> str:
    return str(getattr(settings, "image_oss_access_key_id", None) or getattr(settings, "oss_access_key_id", None) or "").strip()


def _resolve_access_key_secret() -> str:
    return str(getattr(settings, "image_oss_access_key_secret", None) or getattr(settings, "oss_access_key_secret", None) or "").strip()


def _oss_is_configured() -> bool:
    required = (_resolve_endpoint(), _resolve_bucket(), _resolve_access_key_id(), _resolve_access_key_secret())
    return all(bool(str(v or "").strip()) for v in required)


def get_effective_video_storage_mode() -> Literal["local", "oss"]:
    mode = str(getattr(settings, "image_storage_mode", "auto") or "auto").strip().lower()
    if mode == "local":
        return "local"
    if mode == "oss":
        return "oss"
    if mode != "auto":
        logger.warning("Unknown IMAGE_STORAGE_MODE=%s; fallback to auto", mode)

    env = str(getattr(settings, "environment", "") or "").strip().lower()
    if env != "production":
        return "local"
    return "oss" if _oss_is_configured() else "local"


def _create_oss_bucket():
    if not _oss_is_configured():
        raise VideoStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 OSS/S3 视频存储")
    try:
        import oss2  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise VideoStorageNotConfigured("缺少依赖 oss2，请安装后端依赖（backend/pyproject.toml）。") from exc
    auth = oss2.Auth(_resolve_access_key_id(), _resolve_access_key_secret())
    return oss2.Bucket(auth, _resolve_endpoint(), _resolve_bucket())


def _create_s3_client():
    if not _oss_is_configured():
        raise VideoStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 S3/R2 视频存储")
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise VideoStorageNotConfigured("缺少依赖 boto3，请安装后端依赖（backend/pyproject.toml）。") from exc
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=_resolve_endpoint() or None,
        region_name=_resolve_region() or None,
        aws_access_key_id=_resolve_access_key_id() or None,
        aws_secret_access_key=_resolve_access_key_secret() or None,
        config=Config(signature_version="s3v4"),
    )


def _guess_ext(content_type: str) -> str:
    ct = str(content_type or "").strip().lower()
    if ct == "video/mp4":
        return "mp4"
    if ct == "video/webm":
        return "webm"
    guessed = mimetypes.guess_extension(ct) or ""
    guessed = guessed.lstrip(".").lower()
    if guessed in {"mp4", "webm"}:
        return guessed
    return "mp4"


@dataclass(frozen=True)
class StoredVideo:
    object_key: str
    content_type: str
    size_bytes: int


async def store_video_bytes(
    data: bytes,
    *,
    content_type: str = "video/mp4",
) -> StoredVideo:
    if not data:
        raise ValueError("empty video bytes")
    ct = str(content_type or "").strip().lower() or "application/octet-stream"
    ext = _guess_ext(ct)
    object_key = _build_object_key(ext=ext)

    mode = get_effective_video_storage_mode()

    def _put_local() -> None:
        path = _local_path_for_object_key(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _put_oss() -> None:
        bucket = _create_oss_bucket()
        bucket.put_object(object_key, data, headers={"Content-Type": ct})

    def _put_s3() -> None:
        client = _create_s3_client()
        client.put_object(Bucket=_resolve_bucket(), Key=object_key, Body=data, ContentType=ct)

    if mode == "local":
        await anyio.to_thread.run_sync(_put_local)
        return StoredVideo(object_key=object_key, content_type=ct, size_bytes=len(data))

    if not _oss_is_configured():
        raise VideoStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 OSS/S3 视频存储")

    if _oss_backend_kind() == "aliyun_oss":
        await anyio.to_thread.run_sync(_put_oss)
    else:
        await anyio.to_thread.run_sync(_put_s3)

    return StoredVideo(object_key=object_key, content_type=ct, size_bytes=len(data))


def _hmac_signature(object_key: str, expires_at: int) -> str:
    msg = f"{object_key}\n{int(expires_at)}".encode("utf-8")
    secret = str(settings.secret_key or "").encode("utf-8")
    return hmac.new(secret, msg, sha256).hexdigest()


# Cache signed URLs for 5 minutes (300 seconds) to reduce repeated calculations
# We round expires_at to the nearest 5-minute boundary for cache effectiveness
_SIGNED_URL_CACHE_BUCKET_SECONDS = 300


@lru_cache(maxsize=1024)
def _cached_build_signed_url(
    object_key: str,
    api_base: str,
    expires_at_bucket: int,
    ttl: int,
) -> str:
    """
    Cached version of signed URL generation.

    expires_at_bucket is rounded to 5-minute intervals for cache effectiveness.
    The actual expires_at is calculated from the bucket + remaining TTL.
    """
    expires_at = expires_at_bucket + ttl
    sig = _hmac_signature(object_key, expires_at)
    safe_key = quote(object_key, safe="/")
    return f"{api_base}/media/videos/{safe_key}?expires={expires_at}&sig={sig}"


def build_signed_video_url(
    object_key: str,
    *,
    base_url: str | None = None,
    ttl_seconds: int | None = None,
) -> str:
    """
    Generate a signed URL for video access.

    Uses LRU cache with 5-minute time buckets to reduce repeated calculations.
    """
    api_base = (base_url or settings.gateway_api_base_url or "").rstrip("/")
    if not api_base:
        api_base = "http://localhost:8000"

    ttl = int(ttl_seconds or getattr(settings, "image_signed_url_ttl_seconds", 3600) or 3600)

    # Round current time to nearest 5-minute bucket for cache effectiveness
    now = int(time.time())
    bucket = (now // _SIGNED_URL_CACHE_BUCKET_SECONDS) * _SIGNED_URL_CACHE_BUCKET_SECONDS

    return _cached_build_signed_url(object_key, api_base, bucket, ttl)


def verify_signed_video_request(object_key: str, *, expires: int, sig: str) -> None:
    now = int(time.time())
    if int(expires) <= now:
        raise SignedVideoUrlError("signed url expired")

    expected = _hmac_signature(object_key, int(expires))
    if not hmac.compare_digest(str(sig or ""), expected):
        raise SignedVideoUrlError("invalid signature")

    required_prefix = _video_object_prefix()
    if required_prefix and not str(object_key).startswith(required_prefix + "/"):
        raise SignedVideoUrlError("invalid object key prefix")


async def load_video_bytes(object_key: str) -> tuple[bytes, str]:
    if get_effective_video_storage_mode() == "local":
        def _get_local() -> tuple[bytes, str]:
            path = _local_path_for_object_key(object_key)
            body = path.read_bytes()
            guessed = mimetypes.guess_type(path.name)[0] or ""
            content_type = str(guessed or "application/octet-stream")
            return body, content_type

        try:
            return await anyio.to_thread.run_sync(_get_local)
        except Exception:
            logger.exception("Failed to load video from local storage (key=%s)", object_key)
            raise

    if not _oss_is_configured():
        raise VideoStorageNotConfigured("IMAGE_OSS_* 未配置，无法读取 OSS/S3 视频")

    def _get_oss() -> tuple[bytes, str]:
        bucket = _create_oss_bucket()
        result = bucket.get_object(object_key)
        content_type = str(getattr(result, "content_type", None) or "")
        body = result.read()
        if not content_type:
            content_type = "application/octet-stream"
        return body, content_type

    def _get_s3() -> tuple[bytes, str]:
        client = _create_s3_client()
        resp = client.get_object(Bucket=_resolve_bucket(), Key=object_key)
        body = resp["Body"].read() if resp and resp.get("Body") is not None else b""
        content_type = str(resp.get("ContentType") or "application/octet-stream")
        return bytes(body), content_type

    try:
        if _oss_backend_kind() == "aliyun_oss":
            return await anyio.to_thread.run_sync(_get_oss)
        return await anyio.to_thread.run_sync(_get_s3)
    except Exception:
        logger.exception("Failed to load video from OSS/S3 (key=%s)", object_key)
        raise


async def presign_video_get_url(object_key: str, *, expires_seconds: int) -> str:
    if get_effective_video_storage_mode() == "local":
        raise VideoStorageNotConfigured("IMAGE_STORAGE_MODE=local 时不支持生成预签名 URL")
    if not _oss_is_configured():
        raise VideoStorageNotConfigured("IMAGE_OSS_* 未配置，无法生成 OSS/S3 预签名 URL")
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
            Params={"Bucket": _resolve_bucket(), "Key": object_key},
            ExpiresIn=ttl,
        )

    try:
        if _oss_backend_kind() == "aliyun_oss":
            return await anyio.to_thread.run_sync(_sign_oss)
        return await anyio.to_thread.run_sync(_sign_s3)
    except Exception:
        logger.exception("Failed to presign GET url (key=%s)", object_key)
        raise


__all__ = [
    "VideoStorageNotConfigured",
    "SignedVideoUrlError",
    "StoredVideo",
    "build_signed_video_url",
    "get_effective_video_storage_mode",
    "load_video_bytes",
    "presign_video_get_url",
    "store_video_bytes",
    "verify_signed_video_request",
]

