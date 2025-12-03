"""
Helpers for calling Google Gemini via the official google-genai SDK.

These helpers are only used when ProviderConfig.transport == "sdk" so that
we bypass HTTP path concatenation (/v1/...) and rely on the vendor SDK
behaviour instead.
"""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import AsyncIterator, Iterable
from queue import SimpleQueue
from typing import Any

import anyio


class GoogleSDKError(Exception):
    """Raised when the google-genai SDK is unavailable or returns an error."""


def _create_client(api_key: str, base_url: str | None):
    try:
        from google import genai  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise GoogleSDKError(
            "google-genai 未安装，请安装依赖：pip install google-genai"
        ) from exc

    try:
        # 部分版本的 google-genai 不接受 client_options，保持最小参数集。
        return genai.Client(api_key=api_key)
    except Exception as exc:  # pragma: no cover - defensive
        raise GoogleSDKError(f"初始化 google-genai 失败: {exc}") from exc


def _data_url_to_inline_data(url: str) -> dict[str, str] | None:
    """
    Convert a data: URI into inlineData payload accepted by Gemini.
    """
    if not url.startswith("data:"):
        return None
    try:
        header, b64data = url.split(",", 1)
        # Format: data:<mime>;base64,<payload>
        mime_part = header.removeprefix("data:").removesuffix(";base64")
        decoded = base64.b64decode(b64data)
    except Exception:
        return None

    mime_type = mime_part or "application/octet-stream"
    return {"mimeType": mime_type, "data": base64.b64encode(decoded).decode("utf-8")}


def _messages_to_contents(messages: Iterable[Any]) -> list[dict[str, Any]]:
    """
    Convert OpenAI-style messages into Gemini contents shape.
    """
    contents: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or "user"
        parts: list[dict[str, Any]] = []
        content = msg.get("content")
        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("text"), str):
                    parts.append({"text": item["text"]})
                elif item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append({"text": item["text"]})
                elif item.get("type") == "image_url":
                    url = None
                    image_val = item.get("image_url")
                    if isinstance(image_val, dict):
                        url = image_val.get("url")
                    elif isinstance(item.get("url"), str):
                        url = item["url"]
                    if isinstance(url, str):
                        inline = _data_url_to_inline_data(url)
                        if inline:
                            parts.append({"inlineData": inline})
        else:
            parts.append({"text": str(content)})

        contents.append({"role": role, "parts": parts or [{"text": ""}]})
    return contents


def _response_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("to_dict", "model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                continue
    # google-genai objects often support .to_json(); fall back to that.
    to_json = getattr(obj, "to_json", None)
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
    Discover models via SDK. Falls back to empty list on errors.
    """
    client = _create_client(api_key, base_url)

    def _call():
        return list(client.models.list())

    try:
        items = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise GoogleSDKError(f"google-genai 列表接口失败: {exc}") from exc

    return [_response_to_dict(item) for item in items]


async def generate_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> dict[str, Any]:
    """
    Non-streaming generate_content 调用。
    """
    client = _create_client(api_key, base_url)
    contents = payload.get("contents")
    if not contents:
        messages = payload.get("messages") or payload.get("input") or []
        contents = _messages_to_contents(messages)

    def _call():
        return client.models.generate_content(model=model_id, contents=contents)

    try:
        response = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise GoogleSDKError(f"google-genai 调用失败: {exc}") from exc

    return _response_to_dict(response)


async def stream_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Streaming generate_content 调用。使用后台线程消费同步 SDK，
    通过队列把分块传回异步上下文。
    """
    client = _create_client(api_key, base_url)
    contents = payload.get("contents")
    if not contents:
        messages = payload.get("messages") or payload.get("input") or []
        contents = _messages_to_contents(messages)

    queue: SimpleQueue[Any] = SimpleQueue()
    sentinel = object()

    def _worker():
        try:
            for part in client.models.generate_content(
                model=model_id, contents=contents, stream=True
            ):
                queue.put(part)
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
            raise GoogleSDKError(f"google-genai 流式调用失败: {item}") from item
        yield _response_to_dict(item)
