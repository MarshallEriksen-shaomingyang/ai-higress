from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.deps import get_http_client, get_qdrant
from app.models import APIKey, User
from tests.utils import jwt_auth_headers


@pytest.fixture()
def _dummy_http_client_override():
    class DummyClient:
        pass

    async def _override():
        yield DummyClient()

    return _override


def _get_seed_ids(session) -> tuple[str, str]:
    user_id = session.execute(select(User.id)).scalar_one()
    api_key_id = session.execute(select(APIKey.id)).scalar_one()
    return str(user_id), str(api_key_id)


def test_admin_memory_create_requires_project_id(app_with_inmemory_db, _dummy_http_client_override, monkeypatch):
    app, SessionLocal = app_with_inmemory_db

    # Avoid resolving real qdrant/http client deps in tests.
    class FakeQdrant:
        async def put(self, *args, **kwargs):
            return httpx.Response(500, json={"error": "unexpected"})

    async def _override_qdrant():
        return FakeQdrant()

    app.dependency_overrides[get_qdrant] = _override_qdrant
    app.dependency_overrides[get_http_client] = _dummy_http_client_override

    with SessionLocal() as db:
        user_id, _ = _get_seed_ids(db)
        headers = jwt_auth_headers(user_id)

    with TestClient(app) as client:
        resp = client.post("/v1/admin/memories", headers=headers, json={"content": "hello"})
        assert resp.status_code == 422


def test_admin_memory_create_uses_selected_project_id(app_with_inmemory_db, _dummy_http_client_override, monkeypatch):
    app, SessionLocal = app_with_inmemory_db

    with SessionLocal() as db:
        user_id, api_key_id = _get_seed_ids(db)
        headers = jwt_auth_headers(user_id)

    # Ensure global embedding model is configured for this admin operation.
    from app.api.v1 import admin_memory_routes

    monkeypatch.setattr(admin_memory_routes.settings, "kb_global_embedding_logical_model", "test-embed")

    async def _fake_embed_text(*args, **kwargs):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(admin_memory_routes, "embed_text", _fake_embed_text)

    class FakeQdrant:
        async def put(self, path: str, *, params=None, json=None, **kwargs):
            assert path == "/collections/kb_system/points"
            assert params == {"wait": "true"}
            assert json["points"][0]["vector"]["text"] == [0.1, 0.2, 0.3]
            payload = json["points"][0]["payload"]
            assert payload["scope"] == "system"
            assert payload["approved"] is True
            return httpx.Response(200, json={"result": {"status": "ok"}})

    async def _override_qdrant():
        return FakeQdrant()

    app.dependency_overrides[get_qdrant] = _override_qdrant
    app.dependency_overrides[get_http_client] = _dummy_http_client_override

    with TestClient(app) as client:
        resp = client.post(
            "/v1/admin/memories",
            headers=headers,
            json={
                "project_id": api_key_id,
                "content": "hello",
                "categories": ["kb"],
                "keywords": ["x"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "hello"
        assert data["approved"] is True
