"""
SDK 厂商分发与探测。

当前支持 google-genai、openai 与 Claude/Anthropic 官方 SDK，后续新增厂商时在此集中配置。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.schemas import ProviderConfig
from app.provider import claude_sdk, google_sdk, openai_sdk

SDKErrorTypes = tuple[type[BaseException], ...]


@dataclass(frozen=True)
class SDKDriver:
    name: str
    list_models: Callable[..., Awaitable[list[dict]]]
    generate_content: Callable[..., Awaitable[dict]]
    stream_content: Callable[..., AsyncIterator[dict]]
    error_types: SDKErrorTypes


def _normalized_host(base_url: Any) -> str:
    try:
        host = base_url.host  # pydantic HttpUrl
    except Exception:
        parsed = urlparse(str(base_url))
        host = parsed.hostname or ""
    return host.lower()


def normalize_base_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text.rstrip("/")


def detect_sdk_vendor(provider: ProviderConfig) -> str | None:
    """
    根据 provider id 与 base_url 主机名推断使用哪个官方 SDK。
    """
    pid = provider.id.lower()
    host = _normalized_host(provider.base_url)

    if ("openai" in pid or "openai" in host) and "azure" not in pid and "azure" not in host:
        return "openai"

    if any(key in pid for key in ("claude", "anthropic")) or any(
        key in host for key in ("anthropic", "claude.ai")
    ):
        return "claude"

    if any(key in pid for key in ("google", "gemini")) or any(
        key in host for key in ("generativelanguage", "googleapis", "gemini")
    ):
        return "google"

    return None


def get_sdk_driver(provider: ProviderConfig) -> SDKDriver | None:
    vendor = detect_sdk_vendor(provider)
    if vendor == "google":
        return SDKDriver(
            name="google",
            list_models=google_sdk.list_models,
            generate_content=google_sdk.generate_content,
            stream_content=google_sdk.stream_content,
            error_types=(google_sdk.GoogleSDKError,),
        )
    if vendor == "openai":
        return SDKDriver(
            name="openai",
            list_models=openai_sdk.list_models,
            generate_content=openai_sdk.generate_content,
            stream_content=openai_sdk.stream_content,
            error_types=(openai_sdk.OpenAISDKError,),
        )
    if vendor == "claude":
        return SDKDriver(
            name="claude",
            list_models=claude_sdk.list_models,
            generate_content=claude_sdk.generate_content,
            stream_content=claude_sdk.stream_content,
            error_types=(claude_sdk.ClaudeSDKError,),
        )
    return None
