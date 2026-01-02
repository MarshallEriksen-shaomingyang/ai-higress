"""
Provider 公共工具函数

提供 Provider 相关的通用功能：
- URL 检测（Google/OpenAI 等）
- 路径推导（从 chat_completions_path 推导其他 API 路径）
"""
from __future__ import annotations

from urllib.parse import urlsplit


# Google Gemini API 原生域名
_GEMINI_BASE_URL_HOST = "generativelanguage.googleapis.com"

# OpenAI 官方域名（用于判断是否需要过滤扩展字段）
_OPENAI_OFFICIAL_HOSTS: set[str] = {"api.openai.com"}

# 默认 API 路径
_DEFAULT_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"


def is_google_native_provider_base_url(base_url: str) -> bool:
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
    return str(parsed.netloc or "").lower() == _GEMINI_BASE_URL_HOST


def is_openai_official_provider_base_url(base_url: str) -> bool:
    """
    OpenAI 官方 API 对未知字段通常会严格校验；为避免"可选扩展字段"导致请求失败，
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


def google_v1beta_base(base_url: str) -> str:
    """
    获取 Google API 的 v1beta 基础路径。
    """
    base = str(base_url or "").rstrip("/")
    if base.endswith("/v1beta"):
        return base
    return f"{base}/v1beta"


def derive_openai_path(
    provider_chat_path: str | None,
    target: str,
) -> str:
    """
    从 provider 的 chat_completions_path 推导对应的 API 路径。

    Args:
        provider_chat_path: provider 配置的 chat_completions_path
        target: 目标路径类型，如 "audio/speech", "images/generations", "videos"

    Returns:
        推导后的完整路径

    Examples:
        >>> derive_openai_path("/v1/chat/completions", "audio/speech")
        '/v1/audio/speech'
        >>> derive_openai_path("/api/v1/chat/completions", "images/generations")
        '/api/v1/images/generations'
    """
    raw = str(provider_chat_path or _DEFAULT_CHAT_COMPLETIONS_PATH).strip()
    if not raw:
        raw = _DEFAULT_CHAT_COMPLETIONS_PATH

    lowered = raw.lower()
    if "chat/completions" in lowered:
        prefix = raw[: lowered.rfind("chat/completions")]
        return f"{prefix}{target}".replace("//", "/")

    # 回退：直接返回 /v1/{target}
    return f"/v1/{target}"


def derive_openai_audio_speech_path(provider_cfg) -> str:
    """
    从 provider 配置推导 /audio/speech 路径。
    兼容从 chat_completions_path 或 images_generations_path 推导。
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

    return "/v1/audio/speech"


def derive_openai_images_generations_path(provider_chat_path: str | None) -> str:
    """
    从 chat_completions_path 推导 images/generations 路径。
    """
    return derive_openai_path(provider_chat_path, "images/generations")


def derive_openai_videos_path(provider_chat_path: str | None) -> str:
    """
    从 chat_completions_path 推导 videos 路径。
    """
    return derive_openai_path(provider_chat_path, "videos")


def derive_openai_audio_transcriptions_path(provider_chat_path: str | None) -> str:
    """
    从 chat_completions_path 推导 audio/transcriptions 路径。
    """
    return derive_openai_path(provider_chat_path, "audio/transcriptions")


__all__ = [
    "is_google_native_provider_base_url",
    "is_openai_official_provider_base_url",
    "google_v1beta_base",
    "derive_openai_path",
    "derive_openai_audio_speech_path",
    "derive_openai_audio_transcriptions_path",
    "derive_openai_images_generations_path",
    "derive_openai_videos_path",
]
