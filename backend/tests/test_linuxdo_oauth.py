from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.deps import get_http_client, get_redis
from app.models import Identity, User
from app.services.linuxdo_oauth_service import STATE_STORAGE_KEY
from app.services.registration_window_service import create_registration_window
from app.settings import settings
from tests.utils import InMemoryRedis


def _configure_linuxdo(monkeypatch) -> None:
    monkeypatch.setattr(settings, "linuxdo_enabled", True)
    monkeypatch.setattr(settings, "linuxdo_client_id", "test-client-id")
    monkeypatch.setattr(settings, "linuxdo_client_secret", "test-secret")
    monkeypatch.setattr(
        settings,
        "linuxdo_redirect_uri",
        "https://frontend.example.com/callback",
    )


def test_linuxdo_authorize_redirects_and_stores_state(app_with_inmemory_db, monkeypatch):
    app, _ = app_with_inmemory_db
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    _configure_linuxdo(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/auth/oauth/linuxdo/authorize", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    assert params["client_id"][0] == "test-client-id"
    state = params["state"][0]
    state_key = STATE_STORAGE_KEY.format(state=state)
    assert state_key in fake_redis._data  # type: ignore[attr-defined]


def test_linuxdo_callback_creates_user_and_returns_tokens(app_with_inmemory_db, monkeypatch):
    app, SessionLocal = app_with_inmemory_db
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "linuxdo-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/api/user"):
            return httpx.Response(
                200,
                json={
                    "id": 928374,
                    "username": "linuxdo-user",
                    "name": "LinuxDo 昵称",
                    "avatar_template": "https://cdn.example.com/avatar/{size}.png",
                    "active": True,
                },
            )
        return httpx.Response(404)

    async def override_get_http_client():
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as mock_client:
            yield mock_client

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = override_get_http_client
    _configure_linuxdo(monkeypatch)

    start = datetime.now(UTC) - timedelta(minutes=1)
    end = datetime.now(UTC) + timedelta(minutes=5)
    with SessionLocal() as session:
        create_registration_window(
            session,
            start_time=start,
            end_time=end,
            max_registrations=10,
            auto_activate=True,
        )

    headers = {
        "User-Agent": "pytest",
        "X-Forwarded-For": "203.0.113.5",
    }

    with TestClient(app) as client:
        authorize_resp = client.get("/auth/oauth/linuxdo/authorize", follow_redirects=False)
        state = parse_qs(urlparse(authorize_resp.headers["location"]).query)["state"][0]
        callback_resp = client.post(
            "/auth/oauth/callback",
            json={"code": "auth-code", "state": state},
            headers=headers,
        )

    assert callback_resp.status_code == 200, callback_resp.text
    data = callback_resp.json()
    assert data["access_token"]

    # Refresh token should be in cookie, not body
    from app.api.auth_routes import REFRESH_TOKEN_COOKIE_NAME
    assert data.get("refresh_token") is None
    assert REFRESH_TOKEN_COOKIE_NAME in callback_resp.cookies

    assert data["user"]["username"]

    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == "928374@linux.do")
        ).scalar_one()
        assert user.display_name == "LinuxDo 昵称"
        assert user.avatar.endswith("/240.png")
        identity = session.execute(
            select(Identity).where(Identity.user_id == user.id)
        ).scalar_one()
        assert identity.provider == "linuxdo"


def test_linuxdo_callback_blocked_without_registration_window(app_with_inmemory_db, monkeypatch):
    app, SessionLocal = app_with_inmemory_db
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "linuxdo-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/api/user"):
            return httpx.Response(
                200,
                json={
                    "id": 928374,
                    "username": "linuxdo-user",
                    "name": "LinuxDo 昵称",
                    "avatar_template": "https://cdn.example.com/avatar/{size}.png",
                    "active": True,
                },
            )
        return httpx.Response(404)

    async def override_get_http_client():
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as mock_client:
            yield mock_client

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = override_get_http_client
    _configure_linuxdo(monkeypatch)

    with TestClient(app) as client:
        authorize_resp = client.get("/auth/oauth/linuxdo/authorize", follow_redirects=False)
        state = parse_qs(urlparse(authorize_resp.headers["location"]).query)["state"][0]
        callback_resp = client.post(
            "/auth/oauth/callback",
            json={"code": "auth-code", "state": state},
        )

    assert callback_resp.status_code == 403, callback_resp.text
    assert "当前未开放注册窗口" in callback_resp.text

    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == "928374@linux.do")
        ).scalars().first()
        assert user is None


def test_linuxdo_callback_manual_activation_window_requires_admin_activation(
    app_with_inmemory_db, monkeypatch
):
    app, SessionLocal = app_with_inmemory_db
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "linuxdo-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/api/user"):
            return httpx.Response(
                200,
                json={
                    "id": 928374,
                    "username": "linuxdo-user",
                    "name": "LinuxDo 昵称",
                    "avatar_template": "https://cdn.example.com/avatar/{size}.png",
                    "active": True,
                },
            )
        return httpx.Response(404)

    async def override_get_http_client():
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as mock_client:
            yield mock_client

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = override_get_http_client
    _configure_linuxdo(monkeypatch)

    start = datetime.now(UTC) - timedelta(minutes=1)
    end = datetime.now(UTC) + timedelta(minutes=5)
    with SessionLocal() as session:
        create_registration_window(
            session,
            start_time=start,
            end_time=end,
            max_registrations=10,
            auto_activate=False,
        )

    with TestClient(app) as client:
        authorize_resp = client.get("/auth/oauth/linuxdo/authorize", follow_redirects=False)
        state = parse_qs(urlparse(authorize_resp.headers["location"]).query)["state"][0]
        callback_resp = client.post(
            "/auth/oauth/callback",
            json={"code": "auth-code", "state": state},
        )

    assert callback_resp.status_code == 403, callback_resp.text
    assert "等待管理员激活" in callback_resp.text

    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == "928374@linux.do")
        ).scalar_one()
        assert user.is_active is False
        identity = session.execute(
            select(Identity).where(Identity.user_id == user.id)
        ).scalar_one()
        assert identity.provider == "linuxdo"


def test_linuxdo_callback_existing_user_not_blocked_by_closed_window(app_with_inmemory_db, monkeypatch):
    app, SessionLocal = app_with_inmemory_db
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "linuxdo-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/api/user"):
            return httpx.Response(
                200,
                json={
                    "id": 928374,
                    "username": "linuxdo-user",
                    "name": "LinuxDo 昵称",
                    "avatar_template": "https://cdn.example.com/avatar/{size}.png",
                    "active": True,
                },
            )
        return httpx.Response(404)

    async def override_get_http_client():
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as mock_client:
            yield mock_client

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = override_get_http_client
    _configure_linuxdo(monkeypatch)

    start = datetime.now(UTC) - timedelta(minutes=1)
    end = datetime.now(UTC) + timedelta(minutes=5)
    with SessionLocal() as session:
        create_registration_window(
            session,
            start_time=start,
            end_time=end,
            max_registrations=1,
            auto_activate=True,
        )

    with TestClient(app) as client:
        authorize_resp = client.get("/auth/oauth/linuxdo/authorize", follow_redirects=False)
        state = parse_qs(urlparse(authorize_resp.headers["location"]).query)["state"][0]
        first_resp = client.post(
            "/auth/oauth/callback",
            json={"code": "auth-code", "state": state},
        )
        assert first_resp.status_code == 200, first_resp.text

        authorize_resp_2 = client.get("/auth/oauth/linuxdo/authorize", follow_redirects=False)
        state_2 = parse_qs(urlparse(authorize_resp_2.headers["location"]).query)["state"][0]
        second_resp = client.post(
            "/auth/oauth/callback",
            json={"code": "auth-code-2", "state": state_2},
        )

    assert second_resp.status_code == 200, second_resp.text
