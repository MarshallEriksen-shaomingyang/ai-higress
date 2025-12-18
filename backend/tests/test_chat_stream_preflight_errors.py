from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_redis
from app.routes import create_app
from tests.utils import InMemoryRedis, install_inmemory_db


def _build_key() -> AuthenticatedAPIKey:
    return AuthenticatedAPIKey(
        id=uuid4(),
        user_id=uuid4(),
        user_username="tester",
        is_superuser=False,
        name="test",
        is_active=True,
        disabled_reason=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )


def test_chat_stream_model_unavailable_returns_http_400(monkeypatch) -> None:
    """
    流式响应如果在 StreamingResponse 的 iterator 内抛出 HTTPException，
    由于 headers 已发送，FastAPI 的异常处理不会生效，最终表现为服务端 ExceptionGroup 日志。

    这里验证：模型选择/发现等可预判错误，会在构建 StreamingResponse 之前抛出，
    从而返回正常的 400 JSON 错误体给调用方。
    """
    app = create_app()
    install_inmemory_db(app)

    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    api_key = _build_key()

    async def override_require_api_key():
        return api_key

    app.dependency_overrides[require_api_key] = override_require_api_key

    monkeypatch.setattr("app.api.v1.chat_routes.ensure_account_usable", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.api.v1.chat_routes.get_accessible_provider_ids",
        lambda *_a, **_k: {"a4f"},
    )

    async def fake_select(self, **_kwargs):
        raise HTTPException(status_code=400, detail={"message": "model not available"})

    monkeypatch.setattr(
        "app.api.v1.chat.provider_selector.ProviderSelector.select",
        fake_select,
    )

    with TestClient(app, base_url="http://test") as client:
        resp = client.post(
            "/v1/chat/completions",
            headers={"accept": "text/event-stream"},
            json={
                "model": "Mimo V2 Flash",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

    assert resp.status_code == 400
    payload = resp.json()
    assert payload["detail"]["message"] == "model not available"

