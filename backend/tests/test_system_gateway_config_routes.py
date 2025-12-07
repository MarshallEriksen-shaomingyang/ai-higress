from __future__ import annotations

from fastapi.testclient import TestClient

from app.routes import create_app
from app.settings import settings
from tests.utils import install_inmemory_db, jwt_auth_headers, seed_user_and_key


def test_get_gateway_config_accessible_for_authenticated_user():
    """任何登录用户都可以查看网关配置，用于在前端首页展示。"""
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user, _ = seed_user_and_key(
            session,
            token_plain="user-token",
            username="normal-user",
            email="normal@example.com",
            is_superuser=False,
        )
        user_id = str(user.id)

    headers = jwt_auth_headers(user_id)

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.get("/system/gateway-config", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["api_base_url"] == settings.gateway_api_base_url
    assert data["max_concurrent_requests"] == settings.gateway_max_concurrent_requests
    assert data["request_timeout_ms"] == settings.gateway_request_timeout_ms
    assert data["cache_ttl_seconds"] == settings.gateway_cache_ttl_seconds


def test_update_gateway_config_requires_superuser():
    """只有超级管理员可以更新网关配置。"""
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        # 创建一个普通用户
        normal_user, _ = seed_user_and_key(
            session,
            token_plain="user-token",
            username="normal-user",
            email="normal@example.com",
            is_superuser=False,
        )
        normal_id = str(normal_user.id)

    headers = jwt_auth_headers(normal_id)
    payload = {
        "api_base_url": "https://api.example.com",
        "max_concurrent_requests": 500,
        "request_timeout_ms": 15000,
        "cache_ttl_seconds": 1800,
    }

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.put("/system/gateway-config", headers=headers, json=payload)

    assert resp.status_code == 403


def test_update_gateway_config_updates_settings_for_superuser():
    """超级管理员更新网关配置后，应立即反映在 settings 中（含超时与缓存 TTL）。"""
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        admin_user, _ = seed_user_and_key(
            session,
            token_plain="admin-token",
            username="admin-user",
            email="admin2@example.com",
            is_superuser=True,
        )
        admin_id = str(admin_user.id)

    headers = jwt_auth_headers(admin_id)
    payload = {
        "api_base_url": "https://gateway.new-example.com",
        "max_concurrent_requests": 2000,
        "request_timeout_ms": 45000,
        "cache_ttl_seconds": 7200,
    }

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.put("/system/gateway-config", headers=headers, json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["api_base_url"] == payload["api_base_url"]
    assert data["max_concurrent_requests"] == payload["max_concurrent_requests"]
    assert data["request_timeout_ms"] == payload["request_timeout_ms"]
    assert data["cache_ttl_seconds"] == payload["cache_ttl_seconds"]

    # settings 实例也应被更新，后续请求可以读到最新配置。
    assert settings.gateway_api_base_url == payload["api_base_url"]
    assert settings.gateway_max_concurrent_requests == payload["max_concurrent_requests"]
    assert settings.gateway_request_timeout_ms == payload["request_timeout_ms"]
    assert settings.gateway_cache_ttl_seconds == payload["cache_ttl_seconds"]
    # 同步到内部使用的超时和缓存 TTL。
    assert settings.upstream_timeout == payload["request_timeout_ms"] / 1000.0
    assert settings.models_cache_ttl == payload["cache_ttl_seconds"]
