import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so that `import app` works
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.deps import get_http_client, get_redis  # noqa: E402
from app.routes import create_app  # noqa: E402
from app.schemas import LogicalModel, ModelCapability, PhysicalModel, ProviderConfig  # noqa: E402
from app.services.chat_routing_service import (  # noqa: E402
    _build_dynamic_logical_model_for_group,
    _build_provider_headers,
)
from app.settings import settings  # noqa: E402
from app.storage.redis_service import LOGICAL_MODEL_KEY_TEMPLATE  # noqa: E402
from tests.utils import install_inmemory_db  # noqa: E402


class FakeRedis:
    """
    Minimal async Redis replacement used for tests.
    Supports the subset of commands used by the app.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value

    async def lpush(self, key: str, value: str):
        lst = self._data.setdefault(key, [])
        if not isinstance(lst, list):
            lst = []
        lst.insert(0, value)
        self._data[key] = lst

    async def ltrim(self, key: str, start: int, end: int):
        lst = self._data.get(key, [])
        if not isinstance(lst, list):
            return
        if end == -1:
            slice_end = None
        else:
            slice_end = end + 1
        self._data[key] = lst[start:slice_end]

    async def lrange(self, key: str, start: int, end: int):
        lst = self._data.get(key, [])
        if not isinstance(lst, list):
            return []
        if end == -1:
            slice_end = None
        else:
            slice_end = end + 1
        return lst[start:slice_end]

    async def delete(self, key: str):
        self._data.pop(key, None)


fake_redis = FakeRedis()


def _seed_named_logical_model(
    logical_id: str,
    *,
    endpoint_path: str = "/v1/chat/completions",
) -> None:
    logical = LogicalModel(
        logical_id=logical_id,
        display_name=f"{logical_id} Display",
        description=f"Logical model for {logical_id}",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id="mock",
                model_id=logical_id,
                endpoint=f"https://mock.local{endpoint_path}",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=time.time(),
            )
        ],
        enabled=True,
        updated_at=time.time(),
    )
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical.logical_id)
    fake_redis._data[key] = json.dumps(logical.model_dump(), ensure_ascii=False)


def _mock_send(request: httpx.Request) -> httpx.Response:
    """
    Mock transport handler that emulates an upstream LLM API for tests.
    """
    path = request.url.path

    if path.endswith("/v1/models") and request.method == "GET":
        # Return a simple OpenAI-style model list that includes "test-model".
        data = {
            "object": "list",
            "data": [
                {"id": "test-model", "object": "model"},
            ],
        }
        return httpx.Response(200, json=data)

    if path.endswith("/v1/chat/completions") and request.method == "POST":
        body = json.loads(request.content.decode("utf-8"))
        user_messages = [
            m["content"]
            for m in body.get("messages", [])
            if isinstance(m, dict) and m.get("role") == "user"
        ]
        # A simple echo-style response for testing.
        reply = f"你好！你刚才说: {user_messages[-1]}" if user_messages else "你好！"

        data = {
            "id": "cmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(200, json=data)

    if path.endswith("/v1/responses") and request.method == "POST":
        body = json.loads(request.content.decode("utf-8"))
        instructions = body.get("instructions") or ""
        input_value = body.get("input")
        user_text = ""
        if isinstance(input_value, list):
            segments: list[str] = []
            for item in input_value:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            segments.append(part["text"])
                elif isinstance(content, str):
                    segments.append(content)
            user_text = "".join(segments)
        elif isinstance(input_value, str):
            user_text = input_value

        # Build reply with both instructions and user_text
        reply_parts = []
        if instructions:
            reply_parts.append(instructions)
        if user_text:
            reply_parts.append(user_text)
        reply = " - ".join(reply_parts) if reply_parts else "你好！"
        response_payload = {
            "id": "resp-test",
            "object": "response",
            "created": int(time.time()),
            "model": body.get("model"),
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "id": "resp-test-msg-0",
                    "role": "assistant",
                    "content": [{"type": "text", "text": reply}],
                }
            ],
            "output_text": reply,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 8,
                "total_tokens": 18,
            },
            "metadata": body.get("metadata") or {},
        }
        return httpx.Response(200, json=response_payload)

    if path.endswith("/v1/message") and request.method == "POST":
        body = json.loads(request.content.decode("utf-8"))
        user_segments: list[str] = []
        for item in body.get("messages", []):
            if not isinstance(item, dict):
                continue
            if item.get("role") != "user":
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        user_segments.append(part["text"])
            elif isinstance(content, str):
                user_segments.append(content)
        reply_text = (
            f"Claude 模式响应: {user_segments[-1]}" if user_segments else "Claude 模式响应"
        )
        claude_payload = {
            "id": "msg-test",
            "type": "message",
            "role": "assistant",
            "model": body.get("model"),
            "content": [{"type": "text", "text": reply_text}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 12, "output_tokens": 6},
        }
        return httpx.Response(200, json=claude_payload)

    # Default: return 404 to highlight unexpected calls.
    return httpx.Response(404, json={"error": "unexpected mock path", "path": path})


def _mock_send_responses_stream(request: httpx.Request) -> httpx.Response:
    path = request.url.path

    if path.endswith("/v1/responses") and request.method == "POST":
        response_id = "resp-stream"
        created_chunk = {
            "id": response_id,
            "type": "response.created",
            "response": {
                "id": response_id,
                "object": "response",
                "created": 1,
                "model": "test-model",
                "status": "in_progress",
                "output": [],
                "metadata": {},
            },
        }
        delta_chunk = {
            "id": response_id,
            "type": "response.output_text.delta",
            "response_id": response_id,
            "output_index": 0,
            "delta": "Responses 测试",
        }
        output_done_chunk = {
            "id": response_id,
            "type": "response.output_text.done",
            "response_id": response_id,
            "output_index": 0,
        }
        done_chunk = {
            "id": response_id,
            "type": "response.completed",
            "response": {
                "id": response_id,
                "object": "response",
                "created": 1,
                "model": "test-model",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": f"{response_id}-msg-0",
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Responses 测试"}],
                    }
                ],
                "output_text": "Responses 测试",
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": 5,
                    "total_tokens": 10,
                },
                "metadata": {},
            },
        }
        body = "".join(
            f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            for chunk in (created_chunk, delta_chunk, output_done_chunk, done_chunk)
        )
        body += "data: [DONE]\n\n"
        return httpx.Response(
            200,
            content=body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    return httpx.Response(404, json={"error": "unexpected mock path", "path": path})


def _mock_send_claude_message_missing(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/v1/message") and request.method == "POST":
        return httpx.Response(
            404,
            json={
                "error": {
                    "message": "Invalid URL (POST /v1/message)",
                    "type": "invalid_request_error",
                }
            },
        )
    return _mock_send(request)


def _mock_send_claude_stream_fallback(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/v1/message") and request.method == "POST":
        return httpx.Response(
            404,
            json={
                "error": {
                    "message": "Invalid URL (POST /v1/message)",
                    "type": "invalid_request_error",
                }
            },
        )
    if path.endswith("/v1/chat/completions") and request.method == "POST":
        body = "".join(
            (
                "data: {\"id\":\"cmpl-stream\",\"object\":\"chat.completion.chunk\",\"choices\":[{\"delta\":{\"content\":\"Claude Fallback \",\"role\":\"assistant\"},\"index\":0}]}\n\n",
                "data: {\"id\":\"cmpl-stream\",\"object\":\"chat.completion.chunk\",\"choices\":[{\"delta\":{\"content\":\"Stream\"},\"index\":0,\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":5,\"completion_tokens\":6,\"total_tokens\":11}}\n\n",
                "data: [DONE]\n\n",
            )
        )
        return httpx.Response(
            200,
            content=body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
    return _mock_send(request)


def _mock_send_gemini_non_stream(request: httpx.Request) -> httpx.Response:
    path = request.url.path

    if path.endswith("/v1/models") and request.method == "GET":
        data = {
            "object": "list",
            "data": [
                {"id": "gemini-3-pro", "object": "model"},
            ],
        }
        return httpx.Response(200, json=data)

    if path.endswith("/v1/chat/completions") and request.method == "POST":
        data = {
            "id": "gemini-non-stream",
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Gemini 非流式返回"},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }
        return httpx.Response(200, json=data)

    return httpx.Response(404, json={"error": "unexpected mock path", "path": path})


def _mock_send_gemini_stream(request: httpx.Request) -> httpx.Response:
    path = request.url.path

    if path.endswith("/v1/chat/completions") and request.method == "POST":
        chunk_1 = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Gemini 流响应"},
                        ]
                    }
                }
            ]
        }
        chunk_2 = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": " 第二段"},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        body = "".join(
            f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            for chunk in (chunk_1, chunk_2)
        )
        body += "data: [DONE]\n\n"
        return httpx.Response(
            200,
            content=body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    return httpx.Response(404, json={"error": "unexpected mock path", "path": path})


def _mock_send_gemini_image(request: httpx.Request) -> httpx.Response:
    path = request.url.path

    if path.endswith("/v1/models") and request.method == "GET":
        data = {
            "object": "list",
            "data": [
                {"id": "gemini-2.5-flash-image-preview", "object": "model"},
            ],
        }
        return httpx.Response(200, json=data)

    if path.endswith("/v1/chat/completions") and request.method == "POST":
        data = {
            "id": "gemini-image",
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(b"Gemini Inline Image").decode(
                                        "utf-8"
                                    ),
                                }
                            }
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
        }
        return httpx.Response(200, json=data)

    return httpx.Response(404, json={"error": "unexpected mock path", "path": path})


async def override_get_redis():
    return fake_redis


async def override_get_http_client():
    """
    Provide an AsyncClient whose requests are handled by _mock_send.
    """
    transport = httpx.MockTransport(_mock_send)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


async def _override_get_http_client_responses_stream():
    transport = httpx.MockTransport(_mock_send_responses_stream)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


async def _override_get_http_client_claude_missing():
    transport = httpx.MockTransport(_mock_send_claude_message_missing)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


async def _override_get_http_client_claude_stream_fallback():
    transport = httpx.MockTransport(_mock_send_claude_stream_fallback)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


async def _override_get_http_client_gemini_non_stream():
    transport = httpx.MockTransport(_mock_send_gemini_non_stream)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


async def _override_get_http_client_gemini_stream():
    transport = httpx.MockTransport(_mock_send_gemini_stream)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


async def _override_get_http_client_gemini_image():
    transport = httpx.MockTransport(_mock_send_gemini_image)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


def _seed_logical_model() -> None:
    """
    Store a simple LogicalModel for 'test-model' into the fake Redis so
    that /v1/chat/completions can route via the multi-provider layer.
    """
    _seed_named_logical_model("test-model")


def _prepare_basic_app(monkeypatch):
    monkeypatch.setattr(settings, "mask_as_browser", False, raising=False)
    monkeypatch.setattr(settings, "mask_user_agent", "pytest-client", raising=False)
    monkeypatch.setattr(settings, "mask_origin", None, raising=False)
    monkeypatch.setattr(settings, "mask_referer", None, raising=False)
    # Provide a single mock provider configuration so that the routing
    # layer can build headers for the selected upstream.
    cfg = ProviderConfig(
        id="mock",
        name="Mock Provider",
        base_url="https://mock.local",
        api_key="sk-test",  # pragma: allowlist secret
        messages_path="/v1/message",
    )

    def _load_provider_configs():
        return [cfg]

    def _get_provider_config(provider_id: str):
        if provider_id == "mock":
            return cfg
        return None

    monkeypatch.setattr(
        "app.provider.config.load_provider_configs", _load_provider_configs
    )
    monkeypatch.setattr(
        "app.provider.config.get_provider_config", _get_provider_config
    )
    # 让 routes 层使用同样的配置桩，避免使用真实环境变量。
    monkeypatch.setattr("app.routes.load_provider_configs", _load_provider_configs)
    monkeypatch.setattr("app.routes.get_provider_config", _get_provider_config)

    # Seed logical model into fake Redis.
    fake_redis._data.clear()
    _seed_logical_model()

    app = create_app()
    SessionLocal = install_inmemory_db(app)

    # Seed test models into the database using the SessionLocal from install_inmemory_db
    from app.models import Provider, ProviderModel
    db = SessionLocal()
    try:
        # Create mock provider
        provider = Provider(
            provider_id="mock",
            name="Mock Provider",
            base_url="https://mock.local",
            api_key_encrypted=b"test",
            is_active=True,
        )
        db.add(provider)
        db.flush()

        # Add test-model to the database
        model = ProviderModel(
            provider_id=provider.id,
            model_id="test-model",
            is_active=True,
        )
        db.add(model)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Override Redis and HTTP client dependencies.
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = override_get_http_client

    return app


def _prepare_sdk_app(
    monkeypatch,
    model_id: str = "sdk-gemini",
    *,
    provider_id: str = "google-sdk",
    provider_name: str = "Google SDK",
    base_url: str = "https://generativelanguage.googleapis.com",
    api_key: str = "sk-google",
):
    """
    Prepare an app wired with a single SDK-transport provider.
    """
    monkeypatch.setattr(settings, "mask_as_browser", False, raising=False)
    monkeypatch.setattr(settings, "mask_user_agent", "pytest-client", raising=False)
    monkeypatch.setattr(settings, "mask_origin", None, raising=False)
    monkeypatch.setattr(settings, "mask_referer", None, raising=False)

    cfg = ProviderConfig(
        id=provider_id,
        name=provider_name,
        base_url=base_url,
        api_key=api_key,  # pragma: allowlist secret
        transport="sdk",
    )

    def _load_provider_configs():
        return [cfg]

    def _get_provider_config(pid: str):
        if pid == cfg.id:
            return cfg
        return None

    monkeypatch.setattr(
        "app.provider.config.load_provider_configs", _load_provider_configs
    )
    monkeypatch.setattr(
        "app.provider.config.get_provider_config", _get_provider_config
    )
    # 让路由层也使用相同桩，避免读取真实环境里的其它厂商。
    monkeypatch.setattr("app.routes.load_provider_configs", _load_provider_configs)
    monkeypatch.setattr("app.routes.get_provider_config", _get_provider_config)

    fake_redis._data.clear()
    logical = LogicalModel(
        logical_id=model_id,
        display_name=model_id,
        description=f"SDK logical model for {model_id}",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id=provider_id,
                model_id=model_id,
                endpoint=f"https://{provider_id}.local/v1/chat/completions",
                base_weight=1.0,
                region=None,
                max_qps=50,
                meta_hash=None,
                updated_at=time.time(),
            )
        ],
        enabled=True,
        updated_at=time.time(),
    )
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical.logical_id)
    fake_redis._data[key] = json.dumps(logical.model_dump(), ensure_ascii=False)

    app = create_app()
    SessionLocal = install_inmemory_db(app)

    # Seed SDK models into the database using the SessionLocal from install_inmemory_db
    from app.models import Provider, ProviderModel
    db = SessionLocal()
    try:
        # Create SDK provider
        provider = Provider(
            provider_id=provider_id,
            name=provider_name,
            base_url=base_url,
            api_key_encrypted=b"test",
            is_active=True,
        )
        db.add(provider)
        db.flush()

        # Add SDK model to the database
        sdk_model = ProviderModel(
            provider_id=provider.id,
            model_id=model_id,
            is_active=True,
        )
        db.add(sdk_model)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    app.dependency_overrides[get_redis] = override_get_redis
    # HTTP client不会被 SDK 分支真正使用，但依然需要满足 FastAPI 依赖签名。
    app.dependency_overrides[get_http_client] = override_get_http_client
    return app


def test_models_v1_alias(monkeypatch):
    """
    /v1/models 应该作为 /models 的别名返回相同结构。
    """
    app = _prepare_basic_app(monkeypatch)

    with TestClient(app=app, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer timeline",
        }
        resp = client.get("/v1/models", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("data"), list) and data["data"]
        assert any(item.get("id") == "test-model" for item in data["data"])


@pytest.mark.asyncio
async def test_dynamic_logical_model_uses_alias_mapping(monkeypatch):
    """
    动态 LogicalModel 构建应支持 ProviderModel.alias，将别名映射到真实上游模型 ID。
    """

    # 准备一个带别名的 Provider + Model
    cfg = ProviderConfig(
        id="alias-provider",
        name="Alias Provider",
        base_url="https://alias.example.com",
        api_key="test-key",
        api_keys=None,
        models_path="/v1/models",
    )

    class _FakeProvider:
        def __init__(self) -> None:
            self.provider_id = "alias-provider"

            class _FakeModel:
                def __init__(self) -> None:
                    self.model_id = "claude-sonnet-4-5-20250929"
                    self.alias = "claude-sonnet-4-5"

            self.models = [_FakeModel()]

    fake_provider = _FakeProvider()

    # 只返回一个 provider+config 对
    def _load_providers_with_configs(session=None, **kwargs):
        return [(fake_provider, cfg)]

    def _load_provider_configs(session=None, **kwargs):
        return [cfg]

    async def _ensure_models_cached(client, redis, provider, *, ttl_seconds: int = 300):
        # 返回包含真实上游模型 ID 的列表
        return [
            {
                "id": "claude-sonnet-4-5-20250929",
                "model_id": "claude-sonnet-4-5-20250929",
            }
        ]

    monkeypatch.setattr(
        "app.services.chat_routing_service.load_providers_with_configs",
        _load_providers_with_configs,
    )
    monkeypatch.setattr(
        "app.services.chat_routing_service.load_provider_configs",
        _load_provider_configs,
    )
    monkeypatch.setattr(
        "app.services.chat_routing_service.ensure_provider_models_cached",
        _ensure_models_cached,
    )

    # client/redis 参数在桩中不会被真正使用
    async with httpx.AsyncClient() as client:
        logical = await _build_dynamic_logical_model_for_group(
            client=client,
            redis=fake_redis,
            requested_model="claude-sonnet-4-5",
            lookup_model_id="claude-sonnet-4-5",
            api_style="openai",
            db=object(),  # 仅用于触发 load_providers_with_configs 分支
        )

    assert logical is not None
    assert logical.logical_id == "claude-sonnet-4-5"
    assert logical.upstreams, "dynamic logical model should have at least one upstream"
    upstream = logical.upstreams[0]
    # 这里应使用真实上游模型 ID，而非别名
    assert upstream.model_id == "claude-sonnet-4-5-20250929"


def test_chat_greeting_returns_reply(monkeypatch):
    """
    发起一个问候，看是否能拿到正确的回复结构。
    不依赖真实的 Redis 和 A4F，仅测试网关逻辑是否通畅。
    """
    app = _prepare_basic_app(monkeypatch)

    # Use TestClient in an async test by running it in a threadpool.
    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "你好"},
            ],
            "stream": False,
        }
        headers = {
            "Authorization": "Bearer timeline",
        }

        resp = client.post("/v1/chat/completions", json=payload, headers=headers)

        assert resp.status_code == 200
        data = resp.json()

        # Basic OpenAI-style response structure checks.
        assert data.get("object") == "chat.completion"
        assert isinstance(data.get("choices"), list)
        assert data["choices"], "choices should not be empty"

        message = data["choices"][0].get("message", {})
        assert message.get("role") == "assistant"
        assert "你好" in message.get("content", "")


def test_chat_greeting_accepts_x_api_key_header(monkeypatch):
    app = _prepare_basic_app(monkeypatch)

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "你好?"},
            ],
            "stream": False,
        }
        headers = {
            "X-API-Key": "timeline",
        }

        resp = client.post("/v1/chat/completions", json=payload, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("object") == "chat.completion"


def test_responses_endpoint_adapts_payload(monkeypatch):
    """
    /v1/responses 应兼容 Responses API 风格的 instructions/input 字段，
    并将请求透传到上游 /v1/responses。
    """
    app = _prepare_basic_app(monkeypatch)
    _seed_named_logical_model("test-model", endpoint_path="/v1/responses")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "test-model",
            "instructions": "你是一个友好的测试助手",
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "你好，Responses API"},
                    ],
                }
            ],
            "stream": False,
        }
        headers = {
            "Authorization": "Bearer timeline",
        }

        resp = client.post("/v1/responses", json=payload, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("object") == "response"
        assert data.get("status") == "completed"
        assert isinstance(data.get("output"), list) and data["output"]
        first_block = data["output"][0]
        assert first_block["role"] == "assistant"
        text_segments = first_block["content"]
        assert text_segments and text_segments[0]["text"].startswith("你好")
        assert "Responses API" in data.get("output_text", "")


def test_messages_endpoint_overrides_upstream_path(monkeypatch):
    """
    /v1/messages 应该能透传到上游的 /v1/message，以兼容某些 Anthropic 客户端。
    """
    app = _prepare_basic_app(monkeypatch)
    _seed_named_logical_model("claude-model", endpoint_path="/v1/messages")

    recorded_paths: list[str] = []

    async def _override_get_http_client_with_recorder():
        def _send(request: httpx.Request) -> httpx.Response:
            recorded_paths.append(request.url.path)
            return _mock_send(request)

        transport = httpx.MockTransport(_send)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            yield client

    app.dependency_overrides[get_http_client] = _override_get_http_client_with_recorder

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "claude-model",
            "anthropic_version": "2023-06-01",
            "max_tokens": 64,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "请用 Claude 风格问好"}],
                }
            ],
        }
        headers = {
            "Authorization": "Bearer timeline",
        }

        resp = client.post("/v1/messages", json=payload, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("type") == "message"
        assert data.get("role") == "assistant"
        assert recorded_paths, "mock transport should record upstream calls"
        assert recorded_paths[-1].endswith(
            "/v1/message"
        ), f"expected override to /v1/message, got {recorded_paths[-1]}"


def test_claude_messages_fallback_non_stream(monkeypatch):
    app = _prepare_basic_app(monkeypatch)
    _seed_named_logical_model("claude-model", endpoint_path="/v1/messages")
    app.dependency_overrides[get_http_client] = _override_get_http_client_claude_missing

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "claude-model",
            "anthropic_version": "2023-06-01",
            "max_tokens": 32,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Fallback 测试"}],
                }
            ],
        }
        headers = {
            "Authorization": "Bearer timeline",
        }

        resp = client.post("/v1/messages", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("type") == "message"
        assert data.get("role") == "assistant"
        assert data["content"][0]["text"].startswith("你好")


def test_claude_messages_streaming_fallback(monkeypatch):
    app = _prepare_basic_app(monkeypatch)
    _seed_named_logical_model("claude-model", endpoint_path="/v1/messages")
    app.dependency_overrides[
        get_http_client
    ] = _override_get_http_client_claude_stream_fallback

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "claude-model",
            "anthropic_version": "2023-06-01",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "流式 fallback"}],
                }
            ],
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }

        with client.stream("POST", "/v1/messages", json=payload, headers=headers) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")
            assert "Claude Fallback" in body
            assert "event: message_stop" in body


def _seed_failover_logical_model() -> None:
    """
    Logical model with two upstreams so that we can exercise cross-provider
    failover behaviour.
    """
    logical = LogicalModel(
        logical_id="test-model",
        display_name="Test Model",
        description="Test logical model for failover",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id="fail",
                model_id="test-model",
                endpoint="https://fail.local/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=time.time(),
            ),
            PhysicalModel(
                provider_id="ok",
                model_id="test-model",
                endpoint="https://ok.local/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=time.time(),
            ),
        ],
        enabled=True,
        updated_at=time.time(),
    )
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical.logical_id)
    fake_redis._data[key] = json.dumps(logical.model_dump(), ensure_ascii=False)


def _mock_send_failover(request: httpx.Request) -> httpx.Response:
    """
    Transport that makes the first provider return an error and the
    second provider return a valid response so that the gateway must
    fail over.
    """
    host = request.url.host
    path = request.url.path

    if path.endswith("/v1/chat/completions") and request.method == "POST":
        if host == "fail.local":
            return httpx.Response(500, json={"error": "fail-provider"})

        if host == "ok.local":
            body = json.loads(request.content.decode("utf-8"))
            user_messages = [
                m["content"]
                for m in body.get("messages", [])
                if isinstance(m, dict) and m.get("role") == "user"
            ]
            reply = (
                f"来自 ok 提供商的回复: {user_messages[-1]}"
                if user_messages
                else "来自 ok 提供商的回复"
            )
            data = {
                "id": "cmpl-ok",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
            }
            return httpx.Response(200, json=data)

    return httpx.Response(
        404, json={"error": "unexpected mock path", "host": host, "path": path}
    )


async def _override_get_http_client_failover():
    transport = httpx.MockTransport(_mock_send_failover)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


def test_chat_failover_non_stream(monkeypatch):
    """
    当第一个厂商返回 5xx 时，应自动切换到下一个可用厂商并返回正常结果。
    """
    from app.routing.scheduler import CandidateScore  # lazy import for tests

    # Two provider configs so that _build_provider_headers can resolve keys.
    cfg_fail = ProviderConfig(
        id="fail",
        name="Fail Provider",
        base_url="https://fail.local",
        api_key="sk-fail",  # pragma: allowlist secret
    )
    cfg_ok = ProviderConfig(
        id="ok",
        name="OK Provider",
        base_url="https://ok.local",
        api_key="sk-ok",  # pragma: allowlist secret
    )

    def _load_provider_configs():
        return [cfg_fail, cfg_ok]

    def _get_provider_config(provider_id: str):
        if provider_id == "fail":
            return cfg_fail
        if provider_id == "ok":
            return cfg_ok
        return None

    # Force the scheduler to pick the failing provider first so that the
    # failover path is deterministically exercised.
    def _choose_upstream(
        logical_model,
        upstreams,
        metrics_by_provider,
        strategy,
        session=None,
        dynamic_weights=None,
    ):
        scored = [
            CandidateScore(upstream=up, metrics=None, score=1.0) for up in upstreams
        ]
        selected = next(c for c in scored if c.upstream.provider_id == "fail")
        return selected, scored

    monkeypatch.setattr(
        "app.provider.config.load_provider_configs", _load_provider_configs
    )
    monkeypatch.setattr(
        "app.provider.config.get_provider_config", _get_provider_config
    )
    monkeypatch.setattr("app.routes.load_provider_configs", _load_provider_configs)
    monkeypatch.setattr("app.routes.get_provider_config", _get_provider_config)
    monkeypatch.setattr("app.routes.choose_upstream", _choose_upstream)

    # Seed logical model with two upstreams into fake Redis.
    fake_redis._data.clear()
    _seed_failover_logical_model()

    app = create_app()
    install_inmemory_db(app)
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = _override_get_http_client_failover

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "你好，测试 failover"},
            ],
            "stream": False,
        }
        headers = {
            "Authorization": "Bearer timeline",
        }

        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        message = data["choices"][0]["message"]["content"]
        # 应该拿到来自 OK 提供商的回复，说明发生了跨厂商兜底。
        assert "来自 ok 提供商的回复" in message


def test_chat_failover_streaming(monkeypatch):
    """
    流式模式下，当第一个厂商在尚未输出任何内容前返回 5xx，
    应自动切换到下一个厂商并继续以流式输出结果。
    """
    from app.routing.scheduler import CandidateScore  # lazy import for tests

    cfg_fail = ProviderConfig(
        id="fail",
        name="Fail Provider",
        base_url="https://fail.local",
        api_key="sk-fail",  # pragma: allowlist secret
    )
    cfg_ok = ProviderConfig(
        id="ok",
        name="OK Provider",
        base_url="https://ok.local",
        api_key="sk-ok",  # pragma: allowlist secret
    )

    def _load_provider_configs():
        return [cfg_fail, cfg_ok]

    def _get_provider_config(provider_id: str):
        if provider_id == "fail":
            return cfg_fail
        if provider_id == "ok":
            return cfg_ok
        return None

    def _choose_upstream(
        logical_model,
        upstreams,
        metrics_by_provider,
        strategy,
        session=None,
        dynamic_weights=None,
    ):
        scored = [
            CandidateScore(upstream=up, metrics=None, score=1.0) for up in upstreams
        ]
        selected = next(c for c in scored if c.upstream.provider_id == "fail")
        return selected, scored

    monkeypatch.setattr(
        "app.provider.config.load_provider_configs", _load_provider_configs
    )
    monkeypatch.setattr(
        "app.provider.config.get_provider_config", _get_provider_config
    )
    monkeypatch.setattr("app.routes.load_provider_configs", _load_provider_configs)
    monkeypatch.setattr("app.routes.get_provider_config", _get_provider_config)
    monkeypatch.setattr("app.routes.choose_upstream", _choose_upstream)

    fake_redis._data.clear()
    _seed_failover_logical_model()

    app = create_app()
    install_inmemory_db(app)
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = _override_get_http_client_failover

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "你好，测试流式 failover"},
            ],
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }

        with client.stream(
            "POST", "/v1/chat/completions", json=payload, headers=headers
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes())
            text = body.decode("utf-8", errors="ignore")
            # 流式响应内容应该来自 OK 提供商，而不是 fail 提供商的错误。
            assert "来自 ok 提供商的回复" in text
            assert "fail-provider" not in text


def test_responses_streaming_rewrites_sse(monkeypatch):
    app = _prepare_basic_app(monkeypatch)
    app.dependency_overrides[get_http_client] = _override_get_http_client_responses_stream
    _seed_named_logical_model("test-model", endpoint_path="/v1/responses")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "test-model",
            "instructions": "你是一个 SSE 测试助手",
            "input": "流式 Responses",
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }

        with client.stream("POST", "/v1/responses", json=payload, headers=headers) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")
            assert "response.created" in body
            assert "response.output_text.delta" in body
            assert "response.output_text.done" in body
            assert "response.completed" in body
            assert '"response_id":' in body
            assert '"output_index":' in body
            assert "Responses 测试" in body
            assert "data: [DONE]" in body


def test_responses_sync_request_for_gpt_codex(monkeypatch):
    """
    使用 gpt-5.1-codex 模型调用 /v1/responses，验证非流式回归。
    """
    app = _prepare_basic_app(monkeypatch)
    _seed_named_logical_model("gpt-5.1-codex", endpoint_path="/v1/responses")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gpt-5.1-codex",
            "instructions": "你是一名回归测试助手",
            "input": "回归测试请求",
            "stream": False,
        }
        headers = {
            "Authorization": "Bearer timeline",
        }

        resp = client.post("/v1/responses", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "completed"
        assert "output_text" in data
        assert "回归测试请求" in data["output_text"]
        assert "你是一名回归测试助手" in data["output_text"]
        output = data.get("output") or []
        assert output and isinstance(output[0].get("content"), list)
        assert (
            "你是一名回归测试助手" in output[0]["content"][0].get("text", "")
        )


def test_gemini_non_streaming_converted_to_openai(monkeypatch):
    app = _prepare_basic_app(monkeypatch)
    app.dependency_overrides[get_http_client] = _override_get_http_client_gemini_non_stream
    _seed_named_logical_model("gemini-3-pro")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gemini-3-pro",
            "messages": [
                {"role": "user", "content": "测试 Gemini 非流式"},
            ],
        }
        headers = {"Authorization": "Bearer timeline"}
        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("object") == "chat.completion"
        assert data["choices"][0]["message"]["content"].startswith("Gemini 非流式")


def test_gemini_streaming_converted_to_openai(monkeypatch):
    app = _prepare_basic_app(monkeypatch)
    app.dependency_overrides[get_http_client] = _override_get_http_client_gemini_stream
    _seed_named_logical_model("gemini-3-pro")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gemini-3-pro",
            "messages": [
                {"role": "user", "content": "测试 Gemini 流式"},
            ],
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }
        with client.stream("POST", "/v1/chat/completions", json=payload, headers=headers) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")
            assert "chat.completion.chunk" in body
            assert "Gemini 流响应" in body
            assert "data: [DONE]" in body


def test_gemini_image_inline_data_converted(monkeypatch):
    app = _prepare_basic_app(monkeypatch)
    app.dependency_overrides[get_http_client] = _override_get_http_client_gemini_image
    _seed_named_logical_model("gemini-2.5-flash-image-preview")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gemini-2.5-flash-image-preview",
            "messages": [
                {"role": "user", "content": "画一张图片"},
            ],
        }
        headers = {"Authorization": "Bearer timeline"}
        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        assert isinstance(content, list)
        first_segment = content[0]
        assert first_segment["type"] == "image_url"
        url = first_segment["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")


def test_gemini_image_saved_to_file(monkeypatch, tmp_path):
    app = _prepare_basic_app(monkeypatch)
    app.dependency_overrides[get_http_client] = _override_get_http_client_gemini_image
    _seed_named_logical_model("gemini-2.5-flash-image-preview")

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gemini-2.5-flash-image-preview",
            "messages": [
                {"role": "user", "content": "喜羊羊"},
            ],
        }
        headers = {"Authorization": "Bearer timeline"}
        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        encoded_url = content[0]["image_url"]["url"]
        encoded = encoded_url.split(",", 1)[1]
        image_bytes = base64.b64decode(encoded)
        out_path = tmp_path / "test.png"
        out_path.write_bytes(image_bytes)
        assert out_path.exists()


def test_sdk_transport_non_stream(monkeypatch):
    """
    SDK 厂商不应经过 HTTP 路径拼接，直接走 google-genai 分支。
    """
    app = _prepare_sdk_app(monkeypatch, model_id="gemini-sdk-model")

    calls: dict[str, int] = {}

    async def _fake_generate_content(api_key, model_id, payload, base_url):
        calls["generate"] = calls.get("generate", 0) + 1
        assert api_key == "sk-google"  # pragma: allowlist secret
        assert model_id == "gemini-sdk-model"
        return {
            "id": "sdk-response",
            "candidates": [
                {
                    "content": {"parts": [{"text": "SDK 返回"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1,
                "candidatesTokenCount": 1,
                "totalTokenCount": 2,
            },
        }

    async def _fake_stream_content(**kwargs):
        calls["stream"] = calls.get("stream", 0) + 1
        yield {}

    monkeypatch.setattr(
        "app.provider.google_sdk.generate_content", _fake_generate_content
    )
    monkeypatch.setattr(
        "app.provider.google_sdk.stream_content", _fake_stream_content
    )

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gemini-sdk-model",
            "messages": [{"role": "user", "content": "你好，SDK"}],
            "stream": False,
        }
        headers = {"Authorization": "Bearer timeline"}

        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("object") == "chat.completion"
        assert data["choices"][0]["message"]["content"].startswith("SDK 返回")
        assert calls.get("generate") == 1
        assert calls.get("stream", 0) == 0


def test_sdk_transport_streaming(monkeypatch):
    """
    SDK 流式路径应通过 google-genai 分支适配为 OpenAI SSE。
    """
    app = _prepare_sdk_app(monkeypatch, model_id="gemini-sdk-stream")

    calls: dict[str, int] = {}

    async def _fake_generate_content(**kwargs):
        calls["generate"] = calls.get("generate", 0) + 1
        return {}

    async def _fake_stream_content(api_key, model_id, payload, base_url):
        calls["stream"] = calls.get("stream", 0) + 1
        yield {
            "candidates": [{"content": {"parts": [{"text": "SDK 流片段"}]}}],
        }
        yield {
            "candidates": [
                {
                    "content": {"parts": [{"text": " 结束"}]},
                    "finishReason": "STOP",
                }
            ],
        }

    monkeypatch.setattr(
        "app.provider.google_sdk.generate_content", _fake_generate_content
    )
    monkeypatch.setattr(
        "app.provider.google_sdk.stream_content", _fake_stream_content
    )

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gemini-sdk-stream",
            "messages": [{"role": "user", "content": "流式 SDK"}],
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }

        with client.stream(
            "POST", "/v1/chat/completions", json=payload, headers=headers
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")
            assert "SDK 流片段" in body
            assert "data: [DONE]" in body
        assert calls.get("stream") == 1


def test_openai_sdk_transport_non_stream(monkeypatch):
    app = _prepare_sdk_app(
        monkeypatch,
        model_id="gpt-sdk-model",
        provider_id="openai-sdk",
        provider_name="OpenAI SDK",
        base_url="https://api.openai.com",
        api_key="sk-openai",  # pragma: allowlist secret
    )

    calls: dict[str, int] = {}

    async def _fake_generate_content(api_key, model_id, payload, base_url):
        calls["generate"] = calls.get("generate", 0) + 1
        assert api_key == "sk-openai"  # pragma: allowlist secret
        assert model_id == "gpt-sdk-model"
        assert base_url == "https://api.openai.com"
        return {
            "id": "oai-response",
            "object": "chat.completion",
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "OpenAI SDK 回复"},
                    "finish_reason": "stop",
                }
            ],
        }

    async def _fake_stream_content(**kwargs):
        calls["stream"] = calls.get("stream", 0) + 1
        yield {}

    monkeypatch.setattr(
        "app.provider.openai_sdk.generate_content", _fake_generate_content
    )
    monkeypatch.setattr(
        "app.provider.openai_sdk.stream_content", _fake_stream_content
    )

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gpt-sdk-model",
            "messages": [{"role": "user", "content": "你好，OpenAI SDK"}],
            "stream": False,
        }
        headers = {"Authorization": "Bearer timeline"}

        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("object") == "chat.completion"
        assert data["choices"][0]["message"]["content"].startswith("OpenAI SDK 回复")
        assert calls.get("generate") == 1
        assert calls.get("stream", 0) == 0


def test_openai_sdk_transport_streaming(monkeypatch):
    app = _prepare_sdk_app(
        monkeypatch,
        model_id="gpt-sdk-stream",
        provider_id="openai-sdk",
        provider_name="OpenAI SDK",
        base_url="https://api.openai.com",
        api_key="sk-openai",  # pragma: allowlist secret
    )

    calls: dict[str, int] = {}

    async def _fake_generate_content(**kwargs):
        calls["generate"] = calls.get("generate", 0) + 1
        return {}

    async def _fake_stream_content(api_key, model_id, payload, base_url):
        calls["stream"] = calls.get("stream", 0) + 1
        assert api_key == "sk-openai"  # pragma: allowlist secret
        assert model_id == "gpt-sdk-stream"
        assert base_url == "https://api.openai.com"
        yield {
            "id": "chunk-1",
            "object": "chat.completion.chunk",
            "choices": [
                {"index": 0, "delta": {"content": "OpenAI 流片段"}, "finish_reason": None}
            ],
        }
        yield {
            "id": "chunk-1",
            "object": "chat.completion.chunk",
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "stop"},
            ],
        }

    monkeypatch.setattr(
        "app.provider.openai_sdk.generate_content", _fake_generate_content
    )
    monkeypatch.setattr(
        "app.provider.openai_sdk.stream_content", _fake_stream_content
    )

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "gpt-sdk-stream",
            "messages": [{"role": "user", "content": "流式 OpenAI SDK"}],
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }

        with client.stream(
            "POST", "/v1/chat/completions", json=payload, headers=headers
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")
            assert "OpenAI 流片段" in body
            assert "data: [DONE]" in body
        assert calls.get("stream") == 1


def test_openai_sdk_models_list(monkeypatch):
    app = _prepare_sdk_app(
        monkeypatch,
        model_id="gpt-sdk-model",
        provider_id="openai-sdk",
        provider_name="OpenAI SDK",
        base_url="https://api.openai.com",
        api_key="sk-openai",  # pragma: allowlist secret
    )

    calls: dict[str, int] = {}

    async def _fake_list_models(api_key, base_url):
        calls["list"] = calls.get("list", 0) + 1
        assert api_key == "sk-openai"  # pragma: allowlist secret
        assert base_url == "https://api.openai.com"
        return [{"id": "gpt-sdk-model"}]

    monkeypatch.setattr(
        "app.provider.openai_sdk.list_models", _fake_list_models
    )

    with TestClient(app=app, base_url="http://test") as client:
        headers = {"Authorization": "Bearer timeline"}
        resp = client.get("/v1/models", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any(item.get("id") == "gpt-sdk-model" for item in data.get("data", []))
        assert calls.get("list") == 1


def test_claude_sdk_transport_non_stream(monkeypatch):
    app = _prepare_sdk_app(
        monkeypatch,
        model_id="claude-sdk-model",
        provider_id="claude-sdk",
        provider_name="Claude SDK",
        base_url="https://api.anthropic.com",
        api_key="sk-claude",  # pragma: allowlist secret
    )

    calls: dict[str, int] = {}

    async def _fake_generate_content(api_key, model_id, payload, base_url):
        calls["generate"] = calls.get("generate", 0) + 1
        assert api_key == "sk-claude"  # pragma: allowlist secret
        assert model_id == "claude-sdk-model"
        assert base_url == "https://api.anthropic.com"
        return {
            "id": "msg_1",
            "type": "message",
            "model": model_id,
            "content": [{"type": "text", "text": "Claude SDK 回复"}],
        }

    async def _fake_stream_content(**kwargs):
        calls["stream"] = calls.get("stream", 0) + 1
        yield {}

    monkeypatch.setattr(
        "app.provider.claude_sdk.generate_content", _fake_generate_content
    )
    monkeypatch.setattr(
        "app.provider.claude_sdk.stream_content", _fake_stream_content
    )

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "claude-sdk-model",
            "messages": [{"role": "user", "content": "你好，Claude SDK"}],
            "max_tokens": 16,
            "stream": False,
        }
        headers = {"Authorization": "Bearer timeline"}

        resp = client.post("/v1/messages", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("id") == "msg_1"
        assert "Claude SDK 回复" in data["content"][0]["text"]
        assert calls.get("generate") == 1
        assert calls.get("stream", 0) == 0


def test_claude_sdk_transport_streaming(monkeypatch):
    app = _prepare_sdk_app(
        monkeypatch,
        model_id="claude-sdk-stream",
        provider_id="claude-sdk",
        provider_name="Claude SDK",
        base_url="https://api.anthropic.com",
        api_key="sk-claude",  # pragma: allowlist secret
    )

    calls: dict[str, int] = {}

    async def _fake_generate_content(**kwargs):
        calls["generate"] = calls.get("generate", 0) + 1
        return {}

    async def _fake_stream_content(api_key, model_id, payload, base_url):
        calls["stream"] = calls.get("stream", 0) + 1
        assert api_key == "sk-claude"  # pragma: allowlist secret
        assert model_id == "claude-sdk-stream"
        assert base_url == "https://api.anthropic.com"
        yield {"type": "message_start", "message": {"id": "msg_2"}}
        yield {"type": "content_block_delta", "delta": {"text": "Claude SDK 流片段"}}
        yield {"type": "message_stop"}

    monkeypatch.setattr(
        "app.provider.claude_sdk.generate_content", _fake_generate_content
    )
    monkeypatch.setattr(
        "app.provider.claude_sdk.stream_content", _fake_stream_content
    )

    with TestClient(app=app, base_url="http://test") as client:
        payload = {
            "model": "claude-sdk-stream",
            "messages": [{"role": "user", "content": "流式 Claude SDK"}],
            "max_tokens": 32,
            "stream": True,
        }
        headers = {
            "Authorization": "Bearer timeline",
            "Accept": "text/event-stream",
        }

        with client.stream(
            "POST", "/v1/messages", json=payload, headers=headers
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")
            assert "message_start" in body
            assert "Claude SDK 流片段" in body
            assert "data: [DONE]" in body
        assert calls.get("stream") == 1
        assert calls.get("generate", 0) == 0


def test_claude_sdk_models_list(monkeypatch):
    app = _prepare_sdk_app(
        monkeypatch,
        model_id="claude-sdk-model",
        provider_id="claude-sdk",
        provider_name="Claude SDK",
        base_url="https://api.anthropic.com",
        api_key="sk-claude",  # pragma: allowlist secret
    )

    calls: dict[str, int] = {}

    async def _fake_list_models(api_key, base_url):
        calls["list"] = calls.get("list", 0) + 1
        assert api_key == "sk-claude"  # pragma: allowlist secret
        assert base_url == "https://api.anthropic.com"
        return [{"id": "claude-sdk-model"}]

    monkeypatch.setattr("app.provider.claude_sdk.list_models", _fake_list_models)

    with TestClient(app=app, base_url="http://test") as client:
        headers = {"Authorization": "Bearer timeline"}
        resp = client.get("/v1/models", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any(item.get("id") == "claude-sdk-model" for item in data.get("data", []))
        assert calls.get("list") == 1


@pytest.mark.asyncio
async def test_build_provider_headers_openai_style():
    """
    测试 _build_provider_headers 对 OpenAI 风格使用 Authorization: Bearer 头
    """
    from app.provider.key_pool import reset_key_pool

    provider_cfg = ProviderConfig(
        id="test-openai",
        name="Test OpenAI",
        base_url="https://api.openai.com",
        api_key="sk-test-key-123",
    )
    reset_key_pool(provider_cfg.id)

    # 测试 OpenAI 风格（默认）
    headers, key_selection = await _build_provider_headers(
        provider_cfg, redis=None, api_style="openai"
    )

    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer sk-test-key-123"
    assert "x-api-key" not in headers
    assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_build_provider_headers_claude_style():
    """
    测试 _build_provider_headers 对 Claude 风格使用 x-api-key 头
    """
    from app.provider.key_pool import reset_key_pool

    provider_cfg = ProviderConfig(
        id="test-claude",
        name="Test Claude",
        base_url="https://api.anthropic.com",
        api_key="sk-ant-test-key-456",
    )
    reset_key_pool(provider_cfg.id)

    # 测试 Claude 风格
    headers, key_selection = await _build_provider_headers(
        provider_cfg, redis=None, api_style="claude"
    )

    assert "x-api-key" in headers
    assert headers["x-api-key"] == "sk-ant-test-key-456"
    assert "Authorization" not in headers
    assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_build_provider_headers_default_to_openai():
    """
    测试 _build_provider_headers 默认使用 OpenAI 风格
    """
    from app.provider.key_pool import reset_key_pool

    provider_cfg = ProviderConfig(
        id="test-default",
        name="Test Default",
        base_url="https://api.example.com",
        api_key="sk-default-key-789",
    )
    reset_key_pool(provider_cfg.id)

    # 不传 api_style，应该默认为 openai
    headers, key_selection = await _build_provider_headers(
        provider_cfg, redis=None
    )

    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer sk-default-key-789"
    assert "x-api-key" not in headers
