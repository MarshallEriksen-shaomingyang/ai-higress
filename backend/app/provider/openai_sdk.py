"""
Helpers for calling OpenAI via官方 Python SDK。

接口签名与 google_sdk 保持一致，便于在路由/发现流程中做统一分发。
"""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncIterator
from queue import SimpleQueue
from typing import Any

import anyio


class OpenAISDKError(Exception):
    """Raised when the openai SDK is unavailable or returns an error."""


def _create_client(api_key: str, base_url: str | None):
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise OpenAISDKError("openai 未安装，请执行: pip install openai") from exc

    try:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = str(base_url)
        return OpenAI(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        raise OpenAISDKError(f"初始化 openai SDK 失败: {exc}") from exc


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
    to_json = getattr(obj, "model_dump_json", None)
    if callable(to_json):
        try:
            return json.loads(to_json())
        except Exception:
            pass
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"text": str(obj)}


async def list_models(
    *,
    api_key: str,
    base_url: str | None,
) -> list[dict[str, Any]]:
    """
    列出 OpenAI 模型列表，失败时抛出 OpenAISDKError。
    """
    client = _create_client(api_key, base_url)

    def _call():
        return client.models.list()

    try:
        resp = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise OpenAISDKError(f"openai 列表接口失败: {exc}") from exc

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
    非流式 chat.completions 调用。
    """
    client = _create_client(api_key, base_url)
    upstream_payload = dict(payload)
    upstream_payload["model"] = model_id
    upstream_payload.pop("stream", None)

    def _call():
        return client.chat.completions.create(**upstream_payload)

    try:
        resp = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise OpenAISDKError(f"openai 调用失败: {exc}") from exc

    return _response_to_dict(resp)


async def stream_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> AsyncIterator[dict[str, Any]]:
    """
    流式 chat.completions 调用。通过后台线程消费同步 SDK，
    并将分片以 dict 形式传回异步上下文。
    """
    client = _create_client(api_key, base_url)
    upstream_payload = dict(payload)
    upstream_payload["model"] = model_id
    upstream_payload["stream"] = True

    queue: SimpleQueue[Any] = SimpleQueue()
    sentinel = object()

    def _worker():
        try:
            for chunk in client.chat.completions.create(**upstream_payload):
                queue.put(chunk)
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
            raise OpenAISDKError(f"openai 流式调用失败: {item}") from item
        yield _response_to_dict(item)
