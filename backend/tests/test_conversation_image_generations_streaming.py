from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import APIKey, User


def test_create_conversation_image_generation_streaming_sse(client: TestClient, db_session, monkeypatch):
    user = db_session.query(User).first()
    api_key = db_session.query(APIKey).first()
    assert user is not None
    assert api_key is not None

    client.app.dependency_overrides[require_jwt_token] = lambda: AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=bool(user.is_superuser),
        is_active=True,
    )

    async def _fake_execute_inline(**kwargs):
        prompt = kwargs.get("prompt") or ""
        image_request = kwargs.get("image_request") or {}
        model = str(image_request.get("model") or "gpt-image-1")
        return {
            "type": "image_generation",
            "status": "succeeded",
            "prompt": prompt,
            "params": {**image_request, "model": model, "response_format": "url"},
            "images": [
                {
                    "url": "http://localhost:8000/media/images/generated-images/2025/01/01/abc.png?expires=1700000001&sig=deadbeef",
                    "object_key": "generated-images/2025/01/01/abc.png",
                    "revised_prompt": prompt,
                }
            ],
            "created": 1700000000,
        }

    def _fake_build_signed_url(object_key: str, *, base_url: str | None = None, ttl_seconds: int | None = None) -> str:
        return f"http://localhost:8000/media/images/{object_key}?expires=1700000001&sig=deadbeef"

    monkeypatch.setattr("app.api.v1.assistant_routes.execute_image_generation_inline", _fake_execute_inline)
    monkeypatch.setattr("app.api.v1.assistant_routes.build_signed_image_url", _fake_build_signed_url)

    resp = client.post(
        "/v1/assistants",
        json={
            "project_id": str(api_key.id),
            "name": "默认助手",
            "system_prompt": "你是一个测试助手",
            "default_logical_model": "test-model",
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

    with client.stream(
        "POST",
        f"/v1/conversations/{conversation_id}/image-generations",
        json={"prompt": "a cat", "model": "gpt-image-1", "n": 1, "streaming": True},
        headers={"Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events: list[dict] = []
        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else str(line)
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[len("data: ") :]
            if data_str == "[DONE]":
                continue
            events.append(json.loads(data_str))

        event_types = [e.get("type") for e in events]
        assert "message.created" in event_types
        assert "message.completed" in event_types

        created = next(e for e in events if e.get("type") == "message.created")
        assert UUID(created["user_message_id"])
        assert UUID(created["assistant_message_id"])

        completed = next(e for e in events if e.get("type") == "message.completed")
        img = completed.get("image_generation") or {}
        assert img.get("type") == "image_generation"
        assert img.get("status") == "succeeded"
        assert isinstance(img.get("images"), list) and img["images"][0]["url"].startswith("http://localhost:8000/media/images/")

    resp = client.get(f"/v1/conversations/{conversation_id}/messages")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        it.get("role") == "assistant"
        and (it.get("content") or {}).get("type") == "image_generation"
        and isinstance((it.get("content") or {}).get("images"), list)
        for it in items
    )

