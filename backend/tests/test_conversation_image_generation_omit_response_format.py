from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import APIKey, Provider, ProviderAPIKey, User
from app.services.encryption import encrypt_secret


def _seed_provider_with_image_model(db_session, *, provider_id: str, model_id: str) -> None:
    provider = Provider(
        provider_id=provider_id,
        name="Image Provider",
        base_url="https://upstream.example.com",
        transport="http",
        chat_completions_path="/v1/chat/completions",
        images_generations_path="/v1/images/generations",
        static_models=[
            {
                "id": model_id,
                "display_name": model_id,
                "family": model_id,
                "context_length": 8192,
                "capabilities": ["image_generation"],
            }
        ],
    )
    db_session.add(provider)
    db_session.flush()
    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()


def test_conversation_image_generation_response_format_null_is_omitted_in_upstream_payload(
    client: TestClient, db_session, monkeypatch
):
    user = db_session.query(User).first()
    api_key = db_session.query(APIKey).first()
    assert user is not None
    assert api_key is not None

    _seed_provider_with_image_model(db_session, provider_id="openai-like", model_id="nano-banana-pro")

    client.app.dependency_overrides[require_jwt_token] = lambda: AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=bool(user.is_superuser),
        is_active=True,
    )

    seen: dict[str, object] = {}

    async def _fake_call(**kwargs):
        seen["json_body"] = kwargs.get("json_body")
        return httpx.Response(
            200,
            json={
                "created": 1700000000,
                "data": [{"url": "https://upstream.example.com/image.png"}],
            },
        )

    monkeypatch.setattr("app.services.image_app_service.call_upstream_http_with_metrics", _fake_call)

    resp = client.post(
        "/v1/assistants",
        json={
            "project_id": str(api_key.id),
            "name": "默认助手",
            "system_prompt": "你是一个测试助手",
            "default_logical_model": "nano-banana-pro",
        },
    )
    assert resp.status_code == 201
    assistant_id = resp.json()["assistant_id"]

    resp = client.post(
        "/v1/conversations",
        json={"assistant_id": assistant_id, "project_id": str(api_key.id), "title": "test"},
    )
    assert resp.status_code == 201
    conversation_id = resp.json()["conversation_id"]

    # response_format=null 表示“不传给上游，由上游决定返回格式”，但会话侧仍会强制落库 url。
    resp = client.post(
        f"/v1/conversations/{conversation_id}/image-generations",
        json={
            "prompt": "a cat",
            "model": "nano-banana-pro",
            "n": 1,
            "streaming": False,
            "response_format": None,
        },
    )
    assert resp.status_code == 200
    assert isinstance(seen.get("json_body"), dict)
    assert "response_format" not in seen["json_body"]

