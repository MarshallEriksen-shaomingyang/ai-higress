"""
Helpers for calling Google Vertex AI (Gemini) via the official google-genai SDK.

Unlike Gemini Developer API (api_key based), Vertex AI typically relies on
Google Cloud credentials (ADC / service account). For compatibility with the
existing provider storage model, this driver accepts the provider "api_key"
as one of:

- A service account JSON string (recommended).
- A raw OAuth access token string (advanced; non-refreshing).

Project/location are inferred in the following order:
- project: service account "project_id" -> env VERTEXAI_PROJECT/GOOGLE_CLOUD_PROJECT
- location: inferred from base_url (e.g. https://us-central1-aiplatform.googleapis.com/)
            -> env VERTEXAI_LOCATION/GOOGLE_CLOUD_LOCATION -> "us-central1"
"""

from __future__ import annotations

import base64
import json
import os
import threading
from collections.abc import AsyncIterator, Iterable
from queue import SimpleQueue
from typing import Any
from urllib.parse import urlparse

import anyio


class VertexAISDKError(Exception):
    """Raised when Vertex AI SDK configuration is missing or returns an error."""


def _extract_location_from_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    try:
        parsed = urlparse(str(base_url))
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    suffix = "-aiplatform.googleapis.com"
    if host.endswith(suffix) and host != "aiplatform.googleapis.com":
        candidate = host[: -len(suffix)]
        if candidate:
            return candidate
    return None


def _data_url_to_inline_data(url: str) -> dict[str, str] | None:
    if not url.startswith("data:"):
        return None
    try:
        header, b64data = url.split(",", 1)
        mime_part = header.removeprefix("data:").removesuffix(";base64")
        decoded = base64.b64decode(b64data)
    except Exception:
        return None
    mime_type = mime_part or "application/octet-stream"
    return {"mimeType": mime_type, "data": base64.b64encode(decoded).decode("utf-8")}


def _messages_to_contents(messages: Iterable[Any]) -> list[dict[str, Any]]:
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


def _credentials_from_api_key(value: str):
    """
    Return (credentials, project_id_from_credentials).

    - If value is a JSON object string, treat as service account info.
    - Otherwise, treat as an OAuth access token.
    """
    text = (value or "").strip()
    if not text:
        raise VertexAISDKError("Vertex AI: api_key 不能为空（请填写服务账号 JSON 或 access token）")

    if text.startswith("{") and text.endswith("}"):
        try:
            info = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VertexAISDKError(f"Vertex AI: 服务账号 JSON 解析失败: {exc}") from exc
        if not isinstance(info, dict):
            raise VertexAISDKError("Vertex AI: 服务账号 JSON 必须为对象")
        try:
            from google.oauth2 import service_account  # type: ignore
        except ImportError as exc:  # pragma: no cover - import guard
            raise VertexAISDKError(
                "google-auth 未安装或不可用（google-genai 通常会带上）。"
            ) from exc
        try:
            credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise VertexAISDKError(f"Vertex AI: 初始化 service account 凭证失败: {exc}") from exc
        project_id = info.get("project_id") if isinstance(info.get("project_id"), str) else None
        return credentials, project_id

    try:
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise VertexAISDKError(
            "google-auth 未安装或不可用（google-genai 通常会带上）。"
        ) from exc
    credentials = Credentials(token=text)
    return credentials, None


def _create_client(api_key: str, base_url: str | None):
    try:
        from google import genai  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise VertexAISDKError(
            "google-genai 未安装，请安装依赖：pip install google-genai"
        ) from exc

    credentials, project_from_key = _credentials_from_api_key(api_key)
    project = project_from_key or os.getenv("VERTEXAI_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise VertexAISDKError(
            "Vertex AI: 缺少 project 配置（请使用服务账号 JSON，或设置环境变量 VERTEXAI_PROJECT/GOOGLE_CLOUD_PROJECT）"
        )

    location = (
        _extract_location_from_base_url(base_url)
        or os.getenv("VERTEXAI_LOCATION")
        or os.getenv("GOOGLE_CLOUD_LOCATION")
        or "us-central1"
    )

    kwargs: dict[str, Any] = {
        "vertexai": True,
        "project": project,
        "location": location,
        "credentials": credentials,
    }
    try:
        return genai.Client(**kwargs)
    except TypeError:
        # 某些版本可能不支持 credentials 参数；退化为依赖 ADC。
        kwargs.pop("credentials", None)
        try:
            return genai.Client(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            raise VertexAISDKError(f"初始化 Vertex AI google-genai 客户端失败: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise VertexAISDKError(f"初始化 Vertex AI google-genai 客户端失败: {exc}") from exc


def _ensure_model_id_fields(item: dict[str, Any]) -> dict[str, Any]:
    if isinstance(item.get("id"), str):
        item.setdefault("model_id", item.get("id"))
        return item
    name = item.get("name")
    if isinstance(name, str) and "/" in name:
        model_id = name.rsplit("/", 1)[-1]
        if model_id:
            item["id"] = model_id
            item.setdefault("model_id", model_id)
    return item


async def list_models(
    *,
    api_key: str,
    base_url: str | None,
) -> list[dict[str, Any]]:
    client = _create_client(api_key, base_url)

    def _call():
        return list(client.models.list())

    try:
        items = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise VertexAISDKError(f"Vertex AI 列表接口失败: {exc}") from exc

    out: list[dict[str, Any]] = []
    for item in items:
        raw = _response_to_dict(item)
        if not isinstance(raw, dict):
            continue
        out.append(_ensure_model_id_fields(raw))
    return out


async def generate_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> dict[str, Any]:
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
        raise VertexAISDKError(f"Vertex AI 调用失败: {exc}") from exc

    return _response_to_dict(response)


async def stream_content(
    *,
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    base_url: str | None,
) -> AsyncIterator[dict[str, Any]]:
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
            raise VertexAISDKError(f"Vertex AI 流式调用失败: {item}") from item
        yield _response_to_dict(item)

