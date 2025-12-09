from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Notification, Provider, User
from app.services.user_provider_service import (
    get_accessible_provider_ids,
    list_providers_shared_with_user,
    update_provider_shared_users,
)


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


def _create_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_provider(session, owner: User) -> Provider:
    provider = Provider(
        provider_id="owner-provider",
        name="Owner Provider",
        base_url="https://example.com",
        transport="http",
        provider_type="native",
        weight=1.0,
        billing_factor=1.0,
        models_path="/v1/models",
        chat_completions_path="/v1/chat/completions",
        status="healthy",
        visibility="private",
        owner_id=owner.id,
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


def test_update_shared_users_and_accessible_ids(session_factory):
    SessionLocal = session_factory
    with SessionLocal() as session:
        owner = _create_user(session, "owner")
        guest = _create_user(session, "guest")
        other = _create_user(session, "other")
        provider = _create_provider(session, owner)

        # 授权 guest 使用 provider，应切换为 restricted
        updated = update_provider_shared_users(
            session, owner.id, provider.provider_id, [guest.id]
        )
        assert updated.visibility == "restricted"
        assert len(updated.shared_users) == 1
        assert updated.shared_users[0].user_id == guest.id

        notifications = session.execute(select(Notification)).scalars().all()
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.target_type == "users"
        assert notification.target_user_ids == [str(guest.id)]
        assert "私有提供商" in notification.title

        # 相同授权列表不应重复发送通知
        update_provider_shared_users(session, owner.id, provider.provider_id, [guest.id])
        notifications_again = session.execute(select(Notification)).scalars().all()
        assert len(notifications_again) == 1

        # owner / guest 应可访问，其他用户不可访问
        ids_owner = get_accessible_provider_ids(session, owner.id)
        ids_guest = get_accessible_provider_ids(session, guest.id)
        ids_other = get_accessible_provider_ids(session, other.id)

        assert updated.provider_id in ids_owner
        assert updated.provider_id in ids_guest
        assert updated.provider_id not in ids_other

        shared_list = list_providers_shared_with_user(session, guest.id)
        assert any(item.provider_id == updated.provider_id for item in shared_list)

        # 清空授权后，应恢复为 private，且 guest 不再可见
        cleared = update_provider_shared_users(session, owner.id, provider.provider_id, [])
        assert cleared.visibility == "private"
        assert cleared.shared_users == []
        ids_guest_after = get_accessible_provider_ids(session, guest.id)
        assert cleared.provider_id not in ids_guest_after

        shared_list_after = list_providers_shared_with_user(session, guest.id)
        assert shared_list_after == []
