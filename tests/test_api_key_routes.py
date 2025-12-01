from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db, get_redis
from app.models import Base, User
from app.routes import create_app
from app.services.api_key_cache import CACHE_KEY_TEMPLATE
from app.services.api_key_service import derive_api_key_hash
from tests.utils import InMemoryRedis, auth_headers, seed_user_and_key


@pytest.fixture()
def client_with_keys(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    fake_redis = InMemoryRedis()
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    monkeypatch.setattr(
        "app.api.api_key_routes.get_redis_client",
        lambda: fake_redis,
        raising=False,
    )

    with SessionLocal() as session:
        seed_user_and_key(session, token_plain="timeline")

    with TestClient(app, base_url="http://test") as client:
        yield client, SessionLocal, fake_redis

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _get_first_user_id(session_factory: sessionmaker[Session]) -> uuid.UUID:
    with session_factory() as session:
        stmt: Select[tuple[User]] = select(User).order_by(User.created_at.asc())
        user = session.execute(stmt).scalars().first()
        assert user is not None
        return user.id


def test_api_key_crud_flow(client_with_keys):
    client, session_factory, fake_redis = client_with_keys
    user_id = _get_first_user_id(session_factory)

    resp_create = client.post(
        f"/users/{user_id}/api-keys",
        json={"name": "cli", "expiry": "week"},
        headers=auth_headers(),
    )
    assert resp_create.status_code == 201
    created = resp_create.json()
    assert created["token"]
    key_id = created["id"]
    assert created["expiry_type"] == "week"

    cache_key = CACHE_KEY_TEMPLATE.format(key_hash=derive_api_key_hash(created["token"]))
    cached_entry = asyncio.run(fake_redis.get(cache_key))
    assert cached_entry is not None

    resp_list = client.get(
        f"/users/{user_id}/api-keys",
        headers=auth_headers(),
    )
    assert resp_list.status_code == 200
    listed = resp_list.json()
    assert any(item["id"] == key_id for item in listed)

    resp_update = client.put(
        f"/users/{user_id}/api-keys/{key_id}",
        json={"name": "cli-renamed", "expiry": "month"},
        headers=auth_headers(),
    )
    assert resp_update.status_code == 200
    updated = resp_update.json()
    assert updated["name"] == "cli-renamed"
    assert updated["expiry_type"] == "month"

    resp_delete = client.delete(
        f"/users/{user_id}/api-keys/{key_id}",
        headers=auth_headers(),
    )
    assert resp_delete.status_code == 204

    resp_list_after = client.get(
        f"/users/{user_id}/api-keys",
        headers=auth_headers(),
    )
    assert resp_list_after.status_code == 200
    assert all(item["id"] != key_id for item in resp_list_after.json())
    assert asyncio.run(fake_redis.get(cache_key)) is None


def test_non_owner_cannot_manage_other_user(client_with_keys):
    client, session_factory, _ = client_with_keys
    admin_id = _get_first_user_id(session_factory)

    with session_factory() as session:
        seed_user_and_key(
            session,
            token_plain="secondary",
            username="bob",
            email="bob@example.com",
            is_superuser=False,
        )

    resp = client.get(
        f"/users/{admin_id}/api-keys",
        headers=auth_headers("secondary"),
    )
    assert resp.status_code == 403

    resp_forbidden = client.post(
        f"/users/{admin_id}/api-keys",
        json={"name": "should-fail", "expiry": "year"},
        headers=auth_headers("secondary"),
    )
    assert resp_forbidden.status_code == 403
