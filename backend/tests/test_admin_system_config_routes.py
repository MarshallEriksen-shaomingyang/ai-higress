from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.deps import get_http_client
from app.models import SystemConfig, User
from tests.utils import jwt_auth_headers, seed_user_and_key


@pytest.fixture()
def _dummy_http_client_override():
    class DummyClient:
        pass

    async def _override():
        yield DummyClient()

    return _override


def test_admin_system_config_requires_superuser(app_with_inmemory_db, _dummy_http_client_override):
    app, SessionLocal = app_with_inmemory_db
    app.dependency_overrides[get_http_client] = _dummy_http_client_override

    with SessionLocal() as session:
        user, _ = seed_user_and_key(
            session,
            token_plain="user-token",
            username="normal-user",
            email="normal@example.com",
            is_superuser=False,
        )
        headers = jwt_auth_headers(str(user.id))

    with TestClient(app) as client:
        resp = client.post(
            "/v1/admin/system/configs",
            headers=headers,
            json={"key": "X_TEST", "value": "1"},
        )
    assert resp.status_code == 403


def test_admin_system_config_upsert_and_get(app_with_inmemory_db, _dummy_http_client_override):
    app, SessionLocal = app_with_inmemory_db
    app.dependency_overrides[get_http_client] = _dummy_http_client_override

    with SessionLocal() as session:
        user_id = str(session.execute(select(User.id)).scalar_one())
        headers = jwt_auth_headers(user_id)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/admin/system/configs",
            headers=headers,
            json={"key": "X_TEST", "value": "hello", "description": "d"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "X_TEST"
        assert data["value"] == "hello"
        assert data["source"] == "db"

        get_resp = client.get("/v1/admin/system/configs/X_TEST", headers=headers)
        assert get_resp.status_code == 200
        got = get_resp.json()
        assert got["value"] == "hello"
        assert got["source"] == "db"


def test_admin_system_config_kb_global_embedding_model_calls_dimension_check(
    app_with_inmemory_db, _dummy_http_client_override, monkeypatch
):
    app, SessionLocal = app_with_inmemory_db
    app.dependency_overrides[get_http_client] = _dummy_http_client_override

    with SessionLocal() as session:
        user_id = str(session.execute(select(User.id)).scalar_one())
        headers = jwt_auth_headers(user_id)

    from app.api.v1 import admin_system_config_routes

    called = {"ok": False}

    async def _fake_validate(*args, **kwargs):
        called["ok"] = True
        return 1536

    monkeypatch.setattr(admin_system_config_routes, "validate_kb_global_embedding_model_dimension", _fake_validate)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/admin/system/configs",
            headers=headers,
            json={"key": "KB_GLOBAL_EMBEDDING_LOGICAL_MODEL", "value": "test-embed"},
        )

    assert resp.status_code == 200
    assert called["ok"] is True


def test_admin_system_config_kb_global_embedding_model_rejects_on_dimension_mismatch(
    app_with_inmemory_db, _dummy_http_client_override, monkeypatch
):
    app, SessionLocal = app_with_inmemory_db
    app.dependency_overrides[get_http_client] = _dummy_http_client_override

    with SessionLocal() as session:
        user_id = str(session.execute(select(User.id)).scalar_one())
        headers = jwt_auth_headers(user_id)

    from app.api.v1 import admin_system_config_routes

    async def _fake_validate(*args, **kwargs):
        raise HTTPException(status_code=409, detail="mismatch")

    monkeypatch.setattr(admin_system_config_routes, "validate_kb_global_embedding_model_dimension", _fake_validate)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/admin/system/configs",
            headers=headers,
            json={"key": "KB_GLOBAL_EMBEDDING_LOGICAL_MODEL", "value": "bad-embed"},
        )
        assert resp.status_code == 409

    with SessionLocal() as session:
        exists = session.execute(
            select(SystemConfig.id).where(SystemConfig.key == "KB_GLOBAL_EMBEDDING_LOGICAL_MODEL").limit(1)
        ).first()
        assert exists is None

