from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import provider_key_routes
from app.jwt_auth import AuthenticatedUser
from app.models import Base, Provider, User
from app.schemas import ProviderAPIKeyCreateRequest, ProviderAPIKeyUpdateRequest
from tests.utils import seed_user_and_key


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    yield SessionLocal

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


def _seed_provider(session: Session, provider_id: str = "mock-provider") -> Provider:
    provider = Provider(
        provider_id=provider_id,
        name="Mock Provider",
        base_url="https://mock.example.com",
        transport="http",
        provider_type="native",
        weight=1.0,
        models_path="/v1/models",
        status="healthy",
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


def test_provider_key_crud_flow(session_factory):
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建一个超级管理员用户和一个 Provider
        admin_user, _ = seed_user_and_key(session, token_plain="timeline")
        provider = _seed_provider(session, "mock-provider")
        auth_admin = _to_authenticated(admin_user)

        # 创建 API Key
        created = provider_key_routes.create_provider_key_endpoint(
            provider_id=provider.provider_id,
            payload=ProviderAPIKeyCreateRequest(
                key="sk-test-123",
                label="default",
                weight=1.0,
                max_qps=10,
                status="active",
            ),
            db=session,
            current_user=auth_admin,
        )
        assert created.provider_id == provider.provider_id
        assert created.label == "default"
        key_id = created.id

        # 列表查询应能看到刚创建的 key
        listed = provider_key_routes.list_provider_keys_endpoint(
            provider.provider_id,
            db=session,
            current_user=auth_admin,
        )
        assert len(listed) == 1
        assert listed[0].id == key_id
        assert listed[0].provider_id == provider.provider_id

        # 更新 key 的基础信息
        updated = provider_key_routes.update_provider_key_endpoint(
            provider_id=provider.provider_id,
            key_id=key_id,
            payload=ProviderAPIKeyUpdateRequest(
                label="renamed",
                weight=2.0,
                max_qps=20,
                status="inactive",
            ),
            db=session,
            current_user=auth_admin,
        )
        assert updated.label == "renamed"
        assert updated.weight == 2.0
        assert updated.max_qps == 20
        assert updated.status == "inactive"

        # 删除 key 后列表应为空
        provider_key_routes.delete_provider_key_endpoint(
            provider_id=provider.provider_id,
            key_id=key_id,
            db=session,
            current_user=auth_admin,
        )

        listed_after = provider_key_routes.list_provider_keys_endpoint(
            provider.provider_id,
            db=session,
            current_user=auth_admin,
        )
        assert listed_after == []

