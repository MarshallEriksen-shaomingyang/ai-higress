from __future__ import annotations

from sqlalchemy import select

from app.models import Notification, User
from tests.utils import jwt_auth_headers, seed_user_and_key


def _create_user(session, username: str, email: str, *, is_superuser: bool = False) -> User:
    user, _ = seed_user_and_key(
        session,
        token_plain=f"{username}-token",
        username=username,
        email=email,
        is_superuser=is_superuser,
    )
    return user


def _get_admin_user(session) -> User:
    return (
        session.execute(select(User).where(User.is_superuser.is_(True)))
        .scalars()
        .first()
    )


def test_admin_can_create_notification_and_user_can_mark_read(client, db_session):
    admin = _get_admin_user(db_session)
    normal_user = _create_user(db_session, "alice", "alice@example.com")

    admin_headers = jwt_auth_headers(str(admin.id))
    create_payload = {
        "title": "系统维护通知",
        "content": "今晚 23:00 进行短暂维护。",
        "level": "warning",
        "target_type": "all",
    }
    resp = client.post(
        "/v1/admin/notifications", headers=admin_headers, json=create_payload
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["title"] == create_payload["title"]
    assert created["level"] == "warning"

    user_headers = jwt_auth_headers(str(normal_user.id))
    list_resp = client.get("/v1/notifications", headers=user_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["is_read"] is False

    unread_resp = client.get("/v1/notifications/unread-count", headers=user_headers)
    assert unread_resp.status_code == 200
    assert unread_resp.json()["unread_count"] == 1

    mark_resp = client.post(
        "/v1/notifications/read",
        headers=user_headers,
        json={"notification_ids": [created["id"]]},
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["updated_count"] == 1

    unread_after = client.get("/v1/notifications/unread-count", headers=user_headers)
    assert unread_after.status_code == 200
    assert unread_after.json()["unread_count"] == 0


def test_non_admin_cannot_create_notification(client, db_session):
    normal_user = _create_user(db_session, "bob", "bob@example.com")
    headers = jwt_auth_headers(str(normal_user.id))

    resp = client.post(
        "/v1/admin/notifications",
        headers=headers,
        json={
            "title": "test",
            "content": "nope",
            "level": "info",
            "target_type": "all",
        },
    )
    assert resp.status_code == 403


def test_target_user_notification_visibility(client, db_session):
    admin = _get_admin_user(db_session)
    user_a = _create_user(db_session, "user-a", "usera@example.com")
    user_b = _create_user(db_session, "user-b", "userb@example.com")

    admin_headers = jwt_auth_headers(str(admin.id))

    # 发一条只给 user_b 的通知
    resp_targeted = client.post(
        "/v1/admin/notifications",
        headers=admin_headers,
        json={
            "title": "私有通知",
            "content": "仅发给 user_b",
            "level": "info",
            "target_type": "users",
            "target_user_ids": [str(user_b.id)],
        },
    )
    assert resp_targeted.status_code == 201
    targeted_id = resp_targeted.json()["id"]

    # user_a 不应看到
    headers_a = jwt_auth_headers(str(user_a.id))
    list_a = client.get("/v1/notifications", headers=headers_a)
    assert list_a.status_code == 200
    assert list_a.json() == []

    # user_b 能看到并标记已读
    headers_b = jwt_auth_headers(str(user_b.id))
    list_b = client.get("/v1/notifications", headers=headers_b)
    assert list_b.status_code == 200
    items_b = list_b.json()
    assert len(items_b) == 1
    assert items_b[0]["id"] == targeted_id

    mark_resp = client.post(
        "/v1/notifications/read",
        headers=headers_b,
        json={"notification_ids": [targeted_id]},
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["updated_count"] == 1

    # user_a 不能标记他看不到的通知
    deny_resp = client.post(
        "/v1/notifications/read",
        headers=headers_a,
        json={"notification_ids": [targeted_id]},
    )
    assert deny_resp.status_code == 404

    # 数据库里只存在一条通知
    count = db_session.execute(select(Notification)).scalars().all()
    assert len(count) == 1
