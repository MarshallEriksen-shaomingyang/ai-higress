"""
Claude/Anthropic 官方 SDK 调用封装。

仅在 ProviderConfig.transport == "sdk" 时启用，避免和 HTTP 代理路径混用。
"""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncIterator
from queue import SimpleQueue
from typing import Any

import anyio


class ClaudeSDKError(Exception):
    """Raised when the anthropic SDK is unavailable or returns an error."""


def _create_client(api_key: str, base_url: str | None):
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise ClaudeSDKError("anthropic 未安装，请执行: pip install anthropic") from exc

    try:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = str(base_url)
        return Anthropic(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        raise ClaudeSDKError(f"初始化 anthropic SDK 失败: {exc}") from exc


def _response_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                continue
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"text": str(obj)}


def _normalize_payload(payload: dict[str, Any], model_id: str) -> dict[str, Any]:
    upstream_payload = dict(payload)
    upstream_payload["model"] = model_id
    upstream_payload.pop("stream", None)
    upstream_payload.pop("anthropic_version", None)
    # 兼容早期 max_tokens_to_sample 字段。
    if "max_tokens" not in upstream_payload and "max_tokens_to_sample" in upstream_payload:
        upstream_payload["max_tokens"] = upstream_payload.pop("max_tokens_to_sample")
    return upstream_payload


async def list_models(
    *,
    api_key: str,
    base_url: str | None,
) -> list[dict[str, Any]]:
    """
    Discover Anthropic 模型列表。
    """
    client = _create_client(api_key, base_url)

    def _call():
        return client.models.list()

    try:
        resp = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise ClaudeSDKError(f"anthropic 列表接口失败: {exc}") from exc

    # Page 对象通常带 data 字段，先尝试结构化读取。
    if hasattr(resp, "data") and isinstance(resp.data, list):
        return [_response_to_dict(item) for item in resp.data if item is not None]

    payload = _response_to_dict(resp)
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


async def generate_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> dict[str, Any]:
    """
    非流式 messages.create 调用。
    """
    client = _create_client(api_key, base_url)
    upstream_payload = _normalize_payload(payload, model_id)

    def _call():
        return client.messages.create(**upstream_payload)

    try:
        resp = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise ClaudeSDKError(f"anthropic 调用失败: {exc}") from exc

    return _response_to_dict(resp)


async def stream_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> AsyncIterator[dict[str, Any]]:
    """
    流式 messages.stream 调用。使用后台线程消费同步 SDK，并将事件转为 dict。
    """
    client = _create_client(api_key, base_url)
    upstream_payload = _normalize_payload(payload, model_id)

    queue: SimpleQueue[Any] = SimpleQueue()
    sentinel = object()

    def _worker():
        try:
            with client.messages.stream(**upstream_payload) as stream:
                for event in stream:
                    queue.put(event)
        except Exception as exc:  # pragma: no cover - defensive
            queue.put(exc)
        finally:
            queue.put(sentinel)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    while True:
        item = await anyio.to_thread.run_sync(queue.get)
        if item is sentinel:
            break
        if isinstance(item, Exception):
            raise ClaudeSDKError(f"anthropic 流式调用失败: {item}") from item
        yield _response_to_dict(item)
