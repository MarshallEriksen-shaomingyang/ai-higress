"""
SDK 厂商分发与探测。

当前支持 google-genai、openai 与 Claude/Anthropic 官方 SDK，后续新增厂商时在此集中配置。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from app.provider import claude_sdk, google_sdk, openai_sdk

if TYPE_CHECKING:
    from app.schemas import ProviderConfig

SDKErrorTypes = tuple[type[BaseException], ...]


@dataclass(frozen=True)
class SDKDriver:
    name: str
    list_models: Callable[..., Awaitable[list[dict]]]
    generate_content: Callable[..., Awaitable[dict]]
    stream_content: Callable[..., AsyncIterator[dict]]
    error_types: SDKErrorTypes


# 运行时注册表：后续新增 SDK 只需注册 driver，而无需修改其它模块。
SDK_DRIVERS: dict[str, SDKDriver] = {}


def register_sdk_driver(vendor: str, driver: SDKDriver) -> None:
    SDK_DRIVERS[vendor] = driver


def list_registered_sdk_vendors() -> list[str]:
    return sorted(SDK_DRIVERS.keys())


def normalize_base_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text.rstrip("/")


def detect_sdk_vendor(provider: ProviderConfig) -> str | None:
    """
    根据 ProviderConfig 中的 sdk_vendor 显式选择官方 SDK。
    当 transport='sdk' 时，管理员必须在配置中指定 sdk_vendor；否则返回 None。
    """
    return getattr(provider, "sdk_vendor", None)


def get_sdk_driver(provider: ProviderConfig) -> SDKDriver | None:
    vendor = detect_sdk_vendor(provider)
    if vendor is None:
        return None
    return SDK_DRIVERS.get(vendor)


# 注册内置 SDK driver；后续新增厂商时在此调用 register_sdk_driver 即可。
register_sdk_driver(
    "google",
    SDKDriver(
        name="google",
        list_models=google_sdk.list_models,
        generate_content=google_sdk.generate_content,
        stream_content=google_sdk.stream_content,
        error_types=(google_sdk.GoogleSDKError,),
    ),
)
register_sdk_driver(
    "openai",
    SDKDriver(
        name="openai",
        list_models=openai_sdk.list_models,
        generate_content=openai_sdk.generate_content,
        stream_content=openai_sdk.stream_content,
        error_types=(openai_sdk.OpenAISDKError,),
    ),
)
register_sdk_driver(
    "claude",
    SDKDriver(
        name="claude",
        list_models=claude_sdk.list_models,
        generate_content=claude_sdk.generate_content,
        stream_content=claude_sdk.stream_content,
        error_types=(claude_sdk.ClaudeSDKError,),
    ),
)
