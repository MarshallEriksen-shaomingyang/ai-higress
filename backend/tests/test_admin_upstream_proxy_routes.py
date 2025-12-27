from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.deps import get_redis
from app.models import User
from app.proxy_pool import pick_upstream_proxy, report_upstream_proxy_failure
from app.routes import create_app
from app.services.upstream_proxy.redis import mark_available, put_endpoint_proxy_url
from tests.utils import InMemoryRedis, install_inmemory_db, jwt_auth_headers, seed_user_and_key


def _admin_headers(user_id: str) -> dict[str, str]:
    return jwt_auth_headers(user_id)


def test_admin_upstream_proxy_config_requires_superuser():
    app = create_app()
    SessionLocal = install_inmemory_db(app)
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    with SessionLocal() as session:
        user, _ = seed_user_and_key(
            session,
            token_plain="user-token",
            username="normal-user-proxy",
            email="normal-proxy@example.com",
            is_superuser=False,
        )
        user_id = str(user.id)

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.get("/admin/upstream-proxy/config", headers=_admin_headers(user_id))

    assert resp.status_code == 403


def test_admin_can_create_source_and_import_endpoints():
    app = create_app()
    SessionLocal = install_inmemory_db(app)
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    with SessionLocal() as session:
        admin = session.execute(select(User).where(User.is_superuser.is_(True))).scalars().first()
        assert admin is not None
        admin_id = str(admin.id)

    with TestClient(app, base_url="http://testserver") as client:
        # Create a static source.
        resp = client.post(
            "/admin/upstream-proxy/sources",
            headers=_admin_headers(admin_id),
            json={
                "name": "static-proxies",
                "source_type": "static_list",
                "enabled": True,
                "default_scheme": "http",
            },
        )
        assert resp.status_code == 200
        source_id = resp.json()["id"]

        # Import endpoints (webshare-style + full URL).
        resp = client.post(
            "/admin/upstream-proxy/endpoints/import",
            headers=_admin_headers(admin_id),
            json={
                "source_id": source_id,
                "default_scheme": "http",
                "text": "142.111.48.253:7030:user:pass\nsocks5://5.6.7.8:1080",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["inserted_or_updated"] >= 1

        resp = client.get(
            "/admin/upstream-proxy/endpoints",
            headers=_admin_headers(admin_id),
            params={"source_id": source_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(e["scheme"] in {"http", "socks5"} for e in data["endpoints"])


@pytest.mark.asyncio
async def test_pick_upstream_proxy_uses_managed_pool_and_failure_cools_down(monkeypatch):
    fake_redis = InMemoryRedis()

    # Patch runtime redis client used by proxy_pool/report paths.
    monkeypatch.setattr("app.redis_client.get_redis_client", lambda: fake_redis, raising=True)

    await fake_redis.set("upstream_proxy:config:enabled", "1")
    await fake_redis.set("upstream_proxy:config:failure_cooldown_seconds", "120")

    endpoint_id = uuid.uuid4()
    proxy_url = "http://user:pass@1.2.3.4:8080"
    await put_endpoint_proxy_url(fake_redis, endpoint_id=endpoint_id, proxy_url=proxy_url)
    await mark_available(fake_redis, endpoint_id)

    picked = await pick_upstream_proxy()
    assert picked == proxy_url

    await report_upstream_proxy_failure(proxy_url)

    # Removed from available set and placed into cooldown.
    assert await fake_redis.scard("upstream_proxy:available") == 0
    assert await fake_redis.get(f"upstream_proxy:cooldown:{endpoint_id}") == "1"
