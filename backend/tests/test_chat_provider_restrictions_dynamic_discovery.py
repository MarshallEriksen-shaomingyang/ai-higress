from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_redis
from app.routes import create_app
from tests.utils import InMemoryRedis, install_inmemory_db


def _build_key(
    *,
    has_restrictions: bool,
    allowed_provider_ids: list[str],
) -> AuthenticatedAPIKey:
    return AuthenticatedAPIKey(
        id=uuid4(),
        user_id=uuid4(),
        user_username="tester",
        is_superuser=False,
        name="test",
        is_active=True,
        disabled_reason=None,
        has_provider_restrictions=has_restrictions,
        allowed_provider_ids=list(allowed_provider_ids),
    )


@pytest.mark.parametrize(
    "has_restrictions,allowed_ids,expected_ids",
    [
        (False, [], {"88code", "a4f", "runanytime"}),
        (True, ["a4f", "runanytime"], {"a4f", "runanytime"}),
    ],
)
def test_chat_dynamic_discovery_respects_api_key_allowed_providers(
    monkeypatch,
    has_restrictions: bool,
    allowed_ids: list[str],
    expected_ids: set[str],
) -> None:
    """
    动态逻辑模型构建会触发 provider /models 发现流程。

    这里验证：当 API Key 配置了 allowed_provider_ids 时，动态发现只会在
    （用户可访问 provider ∩ allowed_provider_ids）范围内执行，避免访问未选择的 provider。
    """
    app = create_app()
    install_inmemory_db(app)

    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    api_key = _build_key(
        has_restrictions=has_restrictions,
        allowed_provider_ids=allowed_ids,
    )

    async def override_require_api_key():
        return api_key

    app.dependency_overrides[require_api_key] = override_require_api_key

    # 避免测试被积分/权限开关影响。
    monkeypatch.setattr("app.api.v1.chat_routes.ensure_account_usable", lambda *_a, **_k: None)

    # 模拟“用户可访问的 provider”集合里包含一个未被选择的公共 provider（88code）。
    monkeypatch.setattr(
        "app.api.v1.chat_routes.get_accessible_provider_ids",
        lambda *_a, **_k: {"88code", "a4f", "runanytime"},
    )

    captured: dict[str, object] = {}

    async def fake_handle(self, **kwargs):
        captured["effective_provider_ids"] = set(kwargs.get("effective_provider_ids", set()))
        raise HTTPException(status_code=400, detail={"message": "model not available"})

    monkeypatch.setattr("app.api.v1.chat_routes.RequestHandler.handle", fake_handle)

    with TestClient(app, base_url="http://test") as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 400

    assert captured.get("effective_provider_ids") == expected_ids


def test_chat_dynamic_discovery_rejects_when_restrictions_empty_intersection(monkeypatch) -> None:
    app = create_app()
    install_inmemory_db(app)

    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    api_key = _build_key(has_restrictions=True, allowed_provider_ids=["not-accessible"])

    async def override_require_api_key():
        return api_key

    app.dependency_overrides[require_api_key] = override_require_api_key

    monkeypatch.setattr("app.api.v1.chat_routes.ensure_account_usable", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.api.v1.chat_routes.get_accessible_provider_ids",
        lambda *_a, **_k: {"a4f"},
    )

    # 若交集为空，应直接 403，不进入动态模型发现流程。
    async def _should_not_be_called(self, **_kwargs):
        raise AssertionError("handler should not run when intersection is empty")

    monkeypatch.setattr("app.api.v1.chat_routes.RequestHandler.handle", _should_not_be_called)

    with TestClient(app, base_url="http://test") as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 403
