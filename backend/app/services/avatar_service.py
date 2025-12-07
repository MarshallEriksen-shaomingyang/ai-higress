from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.settings import settings


def _is_absolute_url(value: str) -> bool:
    """Return True if the string already represents an absolute URL."""

    if value.startswith("//"):
        return True
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _is_root_relative_path(value: str) -> bool:
    """
    判断是否为以 / 开头的站点内相对路径，例如 /media/avatars/xxx.png。

    对于这类值，我们认为前端可以直接使用，不再二次拼接前缀。
    """

    return value.startswith("/")


def build_avatar_url(avatar_value: str | None) -> str | None:
    """
    根据数据库中存储的 avatar 值构造对前端友好的访问 URL。

    设计约定：
    - 数据库存储的是「key」或相对路径，例如：avatars/<user_id>/<uuid>.png
    - 如果管理员在环境变量中配置了 AVATAR_OSS_BASE_URL，则认为所有 key
      都对应 OSS 中的对象，返回形式为：
        <AVATAR_OSS_BASE_URL>/<key>
    - 否则，默认走本地静态目录，返回形式为：
        <AVATAR_LOCAL_BASE_URL>/<key>
      其中 AVATAR_LOCAL_BASE_URL 默认是 /media/avatars。

    兼容策略：
    - 如果 avatar_value 本身已经是完整 URL（http/https 或 // 开头），直接返回；
    - 如果 avatar_value 是以 / 开头的站点相对路径，也直接返回；
      这样可以兼容已有数据或手动配置的头像 URL。
    """

    if not avatar_value:
        return None

    # 已经是完整 URL，直接透传
    if _is_absolute_url(avatar_value):
        return avatar_value

    # 形如 /media/avatars/xxx.png 的路径，视为网关下的相对路径，
    # 需要补上 GATEWAY_API_BASE_URL 前缀，方便前端直接使用完整 URL。
    if _is_root_relative_path(avatar_value):
        base = settings.gateway_api_base_url.rstrip("/")
        return f"{base}{avatar_value}"

    key = avatar_value.lstrip("/")

    # 如果配置了 OSS 基础 URL，则优先走 OSS
    if settings.avatar_oss_base_url:
        base = settings.avatar_oss_base_url.rstrip("/")
        return f"{base}/{key}"

    # 默认走本地静态目录：<GATEWAY_API_BASE_URL>/<AVATAR_LOCAL_BASE_URL>/<key>
    base_path = settings.avatar_local_base_url or "/media/avatars"
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    base_path = base_path.rstrip("/")
    api_base = settings.gateway_api_base_url.rstrip("/")
    return f"{api_base}{base_path}/{key}"


def get_avatar_file_path(avatar_key: str) -> Path:
    """
    将头像 key 映射到本地磁盘路径。

    - 基础目录由 AVATAR_LOCAL_DIR 控制，默认 backend/media/avatars。
    - key 可以包含子目录，例如 <user_id>/<uuid>.png。
    """

    base_dir = Path(settings.avatar_local_dir)
    return base_dir / avatar_key.lstrip("/")


def ensure_avatar_storage_dir() -> Path:
    """
    确保本地头像存储目录存在，并返回该目录的 Path。

    该函数可在应用启动时调用（例如挂载 StaticFiles 之前），
    避免因为目录不存在导致 FastAPI 启动失败。
    """

    base_dir = Path(settings.avatar_local_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


__all__ = [
    "build_avatar_url",
    "get_avatar_file_path",
    "ensure_avatar_storage_dir",
]
