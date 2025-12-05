from __future__ import annotations

import asyncio
import json
import asyncio
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_key_routes
from app.jwt_auth import AuthenticatedUser
from app.models import Base, Provider, User
from app.schemas import (
    APIKeyAllowedProvidersRequest,
    APIKeyCreateRequest,
    APIKeyExpiry,
    APIKeyUpdateRequest,
)
from app.services.api_key_cache import CACHE_KEY_TEMPLATE
from app.services.api_key_service import derive_api_key_hash
from tests.utils import InMemoryRedis, seed_user_and_key

SEEDED_PROVIDERS = ["mock-alpha", "mock-beta", "mock-gamma"]


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    fake_redis = InMemoryRedis()
    monkeypatch.setattr(
        "app.services.api_key_cache.get_redis_client",
        lambda: fake_redis,
        raising=False,
    )

    yield SessionLocal, fake_redis

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _to_authenticated(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        display_name=user.display_name,
        avatar=user.avatar,
    )


def test_api_key_crud_flow(session_factory):
    SessionLocal, fake_redis = session_factory
    with SessionLocal() as session:
        admin_user, _ = seed_user_and_key(session, token_plain="timeline")
        _seed_providers(session)

        auth_admin = _to_authenticated(admin_user)

        created = api_key_routes.create_api_key_endpoint(
            admin_user.id,
            APIKeyCreateRequest(name="cli", expiry=APIKeyExpiry.WEEK),
            db=session,
            current_user=auth_admin,
        )
        assert created.token
        key_id = created.id
        assert created.expiry_type == APIKeyExpiry.WEEK
        assert created.is_active is True
        assert created.disabled_reason is None
        assert created.has_provider_restrictions is False
        assert created.allowed_provider_ids == []

        cache_key = CACHE_KEY_TEMPLATE.format(key_hash=derive_api_key_hash(created.token))
        cached_entry_raw = asyncio.run(fake_redis.get(cache_key))
        assert cached_entry_raw is not None
        cached_entry = json.loads(cached_entry_raw)
        assert cached_entry["has_provider_restrictions"] is False
        assert cached_entry["allowed_provider_ids"] == []
        assert cached_entry["is_active"] is True
        assert cached_entry["disabled_reason"] is None

        listed = api_key_routes.list_api_keys_endpoint(
            admin_user.id,
            db=session,
            current_user=auth_admin,
        )
        assert any(item.id == key_id for item in listed)

        updated = api_key_routes.update_api_key_endpoint(
            admin_user.id,
            key_id,
            APIKeyUpdateRequest(name="cli-renamed", expiry=APIKeyExpiry.MONTH),
            db=session,
            current_user=auth_admin,
        )
        updated_data = updated.model_dump()
        assert updated_data["name"] == "cli-renamed"
        assert updated_data["expiry_type"] == APIKeyExpiry.MONTH
        assert updated_data["is_active"] is True
        assert updated_data["disabled_reason"] is None
        assert updated_data["has_provider_restrictions"] is False

        api_key_routes.delete_api_key_endpoint(
            admin_user.id,
            key_id,
            db=session,
            current_user=auth_admin,
        )

        listed_after = api_key_routes.list_api_keys_endpoint(
            admin_user.id,
            db=session,
            current_user=auth_admin,
        )
        assert all(item.id != key_id for item in listed_after)
        assert asyncio.run(fake_redis.get(cache_key)) is None


def test_non_owner_cannot_manage_other_user(session_factory):
    SessionLocal, _ = session_factory
    with SessionLocal() as session:
        admin_user, _ = seed_user_and_key(session, token_plain="timeline")
        _seed_providers(session)
        auth_admin = _to_authenticated(admin_user)

        other_user, _ = seed_user_and_key(
            session,
            token_plain="secondary",
            username="bob",
            email="bob@example.com",
            is_superuser=False,
        )
        auth_other = _to_authenticated(other_user)

        with pytest.raises(HTTPException) as exc_info:
            api_key_routes.list_api_keys_endpoint(
                admin_user.id,
                db=session,
                current_user=auth_other,
            )
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            api_key_routes.create_api_key_endpoint(
                admin_user.id,
                APIKeyCreateRequest(name="should-fail", expiry=APIKeyExpiry.YEAR),
                db=session,
                current_user=auth_other,
            )
        assert exc_info.value.status_code == 403

        created = api_key_routes.create_api_key_endpoint(
            other_user.id,
            APIKeyCreateRequest(name="ok", expiry=APIKeyExpiry.NEVER),
            db=session,
            current_user=auth_other,
        )
        assert created.user_id == other_user.id
        assert created.name == "ok"


def test_api_key_provider_restrictions_flow(session_factory):
    SessionLocal, fake_redis = session_factory
    with SessionLocal() as session:
        admin_user, _ = seed_user_and_key(session, token_plain="timeline")
        _seed_providers(session)

        auth_admin = _to_authenticated(admin_user)
        provider_a, provider_b = SEEDED_PROVIDERS[:2]

        created = api_key_routes.create_api_key_endpoint(
            admin_user.id,
            APIKeyCreateRequest(
                name="scoped",
                expiry=APIKeyExpiry.MONTH,
                allowed_provider_ids=[provider_a],
            ),
            db=session,
            current_user=auth_admin,
        )
        key_id = created.id
        assert created.allowed_provider_ids == [provider_a]
        cache_key = CACHE_KEY_TEMPLATE.format(key_hash=derive_api_key_hash(created.token))
        cached_entry = json.loads(asyncio.run(fake_redis.get(cache_key)))
        assert cached_entry["allowed_provider_ids"] == [provider_a]

        allowed = api_key_routes.get_api_key_allowed_providers(
            admin_user.id,
            key_id,
            db=session,
            current_user=auth_admin,
        )
        assert allowed.allowed_provider_ids == [provider_a]

        updated = api_key_routes.set_api_key_allowed_providers(
            admin_user.id,
            key_id,
            APIKeyAllowedProvidersRequest(allowed_provider_ids=[provider_b, provider_a]),
            db=session,
            current_user=auth_admin,
        )
        assert updated.allowed_provider_ids == [provider_a, provider_b]

        api_key_routes.remove_api_key_allowed_provider(
            admin_user.id,
            key_id,
            provider_a,
            db=session,
            current_user=auth_admin,
        )
        after_remove = api_key_routes.get_api_key_allowed_providers(
            admin_user.id,
            key_id,
            db=session,
            current_user=auth_admin,
        )
        assert after_remove.allowed_provider_ids == [provider_b]

        api_key_routes.remove_api_key_allowed_provider(
            admin_user.id,
            key_id,
            provider_b,
            db=session,
            current_user=auth_admin,
        )
        after_clear = api_key_routes.get_api_key_allowed_providers(
            admin_user.id,
            key_id,
            db=session,
            current_user=auth_admin,
        )
        assert after_clear.allowed_provider_ids == []
        assert after_clear.has_provider_restrictions is False

        updated_again = api_key_routes.update_api_key_endpoint(
            admin_user.id,
            key_id,
            APIKeyUpdateRequest(allowed_provider_ids=[provider_a, provider_b]),
            db=session,
            current_user=auth_admin,
        )
        assert updated_again.allowed_provider_ids == [provider_a, provider_b]

        cleared = api_key_routes.update_api_key_endpoint(
            admin_user.id,
            key_id,
            APIKeyUpdateRequest(allowed_provider_ids=[]),
            db=session,
            current_user=auth_admin,
        )
        assert cleared.allowed_provider_ids == []
        assert cleared.has_provider_restrictions is False

        cache_entry_after_clear = json.loads(asyncio.run(fake_redis.get(cache_key)))
        assert cache_entry_after_clear["allowed_provider_ids"] == []
        assert cache_entry_after_clear["has_provider_restrictions"] is False


def _seed_providers(session: Session) -> None:
    for idx, provider_id in enumerate(SEEDED_PROVIDERS):
        provider = Provider(
            provider_id=provider_id,
            name=f"Provider {idx}",
            base_url=f"https://{provider_id}.example.com",
            transport="http",
            provider_type="native",
            weight=1.0,
            models_path="/v1/models",
            status="healthy",
        )
        session.add(provider)
    session.commit()
