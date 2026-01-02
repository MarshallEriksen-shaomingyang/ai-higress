from __future__ import annotations

import base64
import hmac
import mimetypes
import time
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

import anyio

from app.logging_config import logger
from app.settings import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class AudioStorageNotConfigured(RuntimeError):
    pass


class SignedAudioUrlError(RuntimeError):
    pass


_AUDIO_OBJECT_KIND = "user-audio"


def _normalize_prefix(value: str | None) -> str:
    raw = str(value or "").strip().strip("/")
    raw = raw.replace("\\", "/")
    parts = [p for p in raw.split("/") if p]
    return "/".join(parts)


def _audio_object_prefix() -> str:
    # 使用独立的音频前缀，不复用图片前缀
    return _normalize_prefix(_AUDIO_OBJECT_KIND)


def _normalize_user_id(value: str | None) -> str | None:
    raw = str(value or "").strip().strip("/")
    if not raw:
        return None
    return raw


def _build_object_key(*, ext: str, user_id: str | None) -> str:
    prefix = _audio_object_prefix()
    owner = _normalize_user_id(user_id)
    uid = uuid.uuid4().hex
    date_part = time.strftime("%Y/%m/%d", time.gmtime())
    filename = f"{uid}.{ext}"
    if prefix and owner:
        return f"{prefix}/{owner}/{date_part}/{filename}"
    if prefix:
        return f"{prefix}/{date_part}/{filename}"
    return f"{date_part}/{filename}"


def _local_base_dir() -> Path:
    # 使用独立的音频存储目录（与图片目录平级）
    image_dir = Path(str(getattr(settings, "image_local_dir", "") or "")).expanduser()
    audio_dir = image_dir.parent / "audio"
    return audio_dir.resolve()


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
    kind = str(getattr(settings, "oss_provider", None) or getattr(settings, "image_storage_provider", None) or "aliyun_oss").strip().lower()
    if kind not in ("aliyun_oss", "s3"):
        raise AudioStorageNotConfigured(f"unsupported storage provider: {kind}")
    return kind  # type: ignore[return-value]


def _resolve_bucket() -> str:
    return str(getattr(settings, "image_oss_bucket", None) or getattr(settings, "oss_private_bucket", None) or getattr(settings, "oss_public_bucket", None) or "").strip()


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


def get_effective_audio_storage_mode() -> Literal["local", "oss"]:
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
        raise AudioStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 OSS/S3 音频存储")
    try:
        import oss2  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise AudioStorageNotConfigured("缺少依赖 oss2，请安装后端依赖（backend/pyproject.toml）。") from exc
    auth = oss2.Auth(_resolve_access_key_id(), _resolve_access_key_secret())
    return oss2.Bucket(auth, _resolve_endpoint(), _resolve_bucket())


def _create_s3_client():
    if not _oss_is_configured():
        raise AudioStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 S3/R2 音频存储")
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise AudioStorageNotConfigured("缺少依赖 boto3，请安装后端依赖（backend/pyproject.toml）。") from exc
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=_resolve_endpoint() or None,
        region_name=_resolve_region() or None,
        aws_access_key_id=_resolve_access_key_id() or None,
        aws_secret_access_key=_resolve_access_key_secret() or None,
        config=Config(signature_version="s3v4"),
    )


def _guess_ext(content_type: str, filename: str | None = None) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"wav", "mp3"}:
            return ext
    ct = str(content_type or "").strip().lower()
    if ct in {"audio/wav", "audio/x-wav", "audio/wave"}:
        return "wav"
    if ct in {"audio/mpeg", "audio/mp3"}:
        return "mp3"
    guessed = mimetypes.guess_extension(ct) or ""
    guessed = guessed.lstrip(".").lower()
    if guessed in {"wav", "mp3"}:
        return guessed
    return "wav"


@dataclass(frozen=True)
class StoredAudio:
    object_key: str
    content_type: str
    size_bytes: int
    is_duplicate: bool = False  # 是否为已存在的重复文件


async def store_audio_bytes(
    data: bytes,
    *,
    content_type: str,
    filename: str | None = None,
    user_id: str | None = None,
    db: "Session | None" = None,
) -> StoredAudio:
    """
    存储音频文件。

    Args:
        data: 音频二进制数据
        content_type: MIME 类型
        filename: 可选的原始文件名
        user_id: 可选的用户 ID（用于路径隔离和去重）
        db: 可选的数据库会话（传入时启用去重检查）

    Returns:
        StoredAudio 包含存储信息，is_duplicate 表示是否为重复文件
    """
    if not data:
        raise ValueError("empty audio bytes")
    ct = str(content_type or "").strip().lower() or "application/octet-stream"
    ext = _guess_ext(ct, filename=filename)

    # 如果提供了数据库会话，进行去重检查
    if db is not None:
        from app.services.file_hash_service import (
            compute_content_hash,
            find_existing_file,
            register_file_hash,
        )

        content_hash = compute_content_hash(data)
        existing = find_existing_file(
            db,
            content_hash=content_hash,
            file_type="audio",
            owner_id=user_id,
        )
        if existing is not None:
            logger.info(
                "audio_dedup_hit",
                content_hash=content_hash[:16],
                existing_key=existing.object_key,
                user_id=user_id,
            )
            return StoredAudio(
                object_key=existing.object_key,
                content_type=existing.content_type,
                size_bytes=existing.size_bytes,
                is_duplicate=True,
            )

    object_key = _build_object_key(ext=ext, user_id=user_id)

    mode = get_effective_audio_storage_mode()

    def _put_local() -> None:
        path = _local_path_for_object_key(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _put_oss() -> None:
        bucket = _create_oss_bucket()
        bucket.put_object(object_key, data, headers={"Content-Type": ct})

    def _put_s3() -> None:
        client = _create_s3_client()
        client.put_object(
            Bucket=_resolve_bucket(),
            Key=object_key,
            Body=data,
            ContentType=ct,
        )

    if mode == "local":
        await anyio.to_thread.run_sync(_put_local)
    elif not _oss_is_configured():
        raise AudioStorageNotConfigured("IMAGE_OSS_* 未配置，无法启用 OSS/S3 音频存储")
    else:
        kind = _oss_backend_kind()
        if kind == "aliyun_oss":
            await anyio.to_thread.run_sync(_put_oss)
        else:
            await anyio.to_thread.run_sync(_put_s3)

    # 存储成功后注册文件哈希（如果提供了数据库会话）
    if db is not None:
        from app.services.file_hash_service import compute_content_hash, register_file_hash

        content_hash = compute_content_hash(data)
        register_file_hash(
            db,
            content_hash=content_hash,
            file_type="audio",
            object_key=object_key,
            content_type=ct,
            size_bytes=len(data),
            owner_id=user_id,
        )

    return StoredAudio(object_key=object_key, content_type=ct, size_bytes=len(data))


def _hmac_signature(object_key: str, expires_at: int) -> str:
    msg = f"{object_key}\n{int(expires_at)}".encode("utf-8")
    secret = str(settings.secret_key or "").encode("utf-8")
    return hmac.new(secret, msg, sha256).hexdigest()


def build_signed_audio_url(
    object_key: str,
    *,
    base_url: str | None = None,
    ttl_seconds: int | None = None,
) -> str:
    api_base = (base_url or settings.gateway_api_base_url or "").rstrip("/")
    if not api_base:
        api_base = "http://localhost:8000"

    ttl = int(ttl_seconds or getattr(settings, "image_signed_url_ttl_seconds", 3600) or 3600)
    expires_at = int(time.time()) + max(1, ttl)
    sig = _hmac_signature(object_key, expires_at)
    safe_key = quote(object_key, safe="/")
    return f"{api_base}/media/audio/{safe_key}?expires={expires_at}&sig={sig}"


def verify_signed_audio_request(object_key: str, *, expires: int, sig: str) -> None:
    now = int(time.time())
    if int(expires) <= now:
        raise SignedAudioUrlError("signed url expired")

    expected = _hmac_signature(object_key, int(expires))
    if not hmac.compare_digest(str(sig or ""), expected):
        raise SignedAudioUrlError("invalid signature")

    required_prefix = _audio_object_prefix()
    if required_prefix and not str(object_key).startswith(required_prefix + "/"):
        raise SignedAudioUrlError("invalid object key prefix")


def assert_audio_object_key_for_user(object_key: str, *, user_id: str) -> None:
    """
    校验 object_key 是否属于指定用户的“用户音频”命名空间。

    说明：
    - 用于消息发送等内部路径，避免用户通过伪造 object_key 读取/引用其他对象；
    - 仅做前缀约束，不校验文件是否存在（存在性由后续 load/presign 决定）。
    """
    required_prefix = _audio_object_prefix()
    owner = _normalize_user_id(user_id)
    if not owner:
        raise ValueError("invalid user_id")
    expected = f"{required_prefix}/{owner}/" if required_prefix else f"{owner}/"
    if not str(object_key).startswith(expected):
        raise ValueError("invalid audio object key for user")


async def load_audio_bytes(object_key: str) -> tuple[bytes, str]:
    if get_effective_audio_storage_mode() == "local":
        def _get_local() -> tuple[bytes, str]:
            path = _local_path_for_object_key(object_key)
            body = path.read_bytes()
            guessed = mimetypes.guess_type(path.name)[0] or ""
            content_type = str(guessed or "application/octet-stream")
            return body, content_type

        try:
            return await anyio.to_thread.run_sync(_get_local)
        except Exception:
            logger.exception("Failed to load audio from local storage (key=%s)", object_key)
            raise

    if not _oss_is_configured():
        raise AudioStorageNotConfigured("IMAGE_OSS_* 未配置，无法读取 OSS/S3 音频")

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
        logger.exception("Failed to load audio from OSS/S3 (key=%s)", object_key)
        raise


async def presign_audio_get_url(object_key: str, *, expires_seconds: int) -> str:
    if get_effective_audio_storage_mode() == "local":
        raise AudioStorageNotConfigured("IMAGE_STORAGE_MODE=local 时不支持生成预签名 URL")
    if not _oss_is_configured():
        raise AudioStorageNotConfigured("IMAGE_OSS_* 未配置，无法生成 OSS/S3 预签名 URL")
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


def encode_audio_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


__all__ = [
    "AudioStorageNotConfigured",
    "SignedAudioUrlError",
    "StoredAudio",
    "assert_audio_object_key_for_user",
    "build_signed_audio_url",
    "encode_audio_base64",
    "get_effective_audio_storage_mode",
    "load_audio_bytes",
    "presign_audio_get_url",
    "store_audio_bytes",
    "verify_signed_audio_request",
]
