from __future__ import annotations

import pytest
from sqlalchemy import select

from app.deps import get_redis
from app.models import Notification, Provider, ProviderSubmission, User
from app.schemas import ProviderValidationResult, UserProviderCreateRequest
from app.schemas.provider_control import ProviderSubmissionRequest
from app.services.provider_submission_service import create_submission
from app.services.user_permission_service import UserPermissionService
from app.services.user_provider_service import create_private_provider
from tests.utils import InMemoryRedis, jwt_auth_headers, seed_user_and_key


def _create_user(session, username: str, email: str, is_superuser: bool = False) -> User:
    user, _ = seed_user_and_key(
        session,
        token_plain=f"{username}-token",
        username=username,
        email=email,
        is_superuser=is_superuser,
    )
    return user


def test_get_my_submissions_returns_only_current_user_records(client, db_session):
    # 准备两个普通用户
    user1 = _create_user(db_session, "user1", "user1@example.com")
    user2 = _create_user(db_session, "user2", "user2@example.com")

    # 为两个用户分别创建提交记录
    sub1 = ProviderSubmission(
        user_id=user1.id,
        name="User1 Provider A",
        provider_id="user1-provider-a",
        base_url="https://api.user1-a.example.com",
        provider_type="native",
        description="User1 submission A",
        approval_status="pending",
    )
    sub2 = ProviderSubmission(
        user_id=user1.id,
        name="User1 Provider B",
        provider_id="user1-provider-b",
        base_url="https://api.user1-b.example.com",
        provider_type="aggregator",
        description="User1 submission B",
        approval_status="approved",
    )
    sub_other = ProviderSubmission(
        user_id=user2.id,
        name="User2 Provider C",
        provider_id="user2-provider-c",
        base_url="https://api.user2-c.example.com",
        provider_type="native",
        description="User2 submission C",
        approval_status="rejected",
    )

    db_session.add_all([sub1, sub2, sub_other])
    db_session.commit()
    db_session.refresh(sub1)
    db_session.refresh(sub2)
    db_session.refresh(sub_other)

    headers = jwt_auth_headers(str(user1.id))

    # 不带筛选参数，返回当前用户的全部提交
    resp = client.get("/providers/submissions/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = {item["id"] for item in data}
    assert ids == {str(sub1.id), str(sub2.id)}
    assert all(item["user_id"] == str(user1.id) for item in data)

    # 按状态过滤，只返回 approved 的记录
    resp_filtered = client.get(
        "/providers/submissions/me",
        headers=headers,
        params={"status": "approved"},
    )
    assert resp_filtered.status_code == 200
    filtered = resp_filtered.json()
    assert len(filtered) == 1
    assert filtered[0]["id"] == str(sub2.id)
    assert filtered[0]["approval_status"] == "approved"
    assert filtered[0]["user_id"] == str(user1.id)


def test_get_my_submissions_requires_authentication(client, db_session):
    # 没有认证头时应返回 401
    resp = client.get("/providers/submissions/me")
    assert resp.status_code == 401


def test_submit_provider_rejects_existing_provider_id(client, db_session, monkeypatch):
    # 先插入一个已存在的公共 Provider 占用 provider_id
    existing_provider = Provider(
        provider_id="dup-provider",
        name="Existing Provider",
        base_url="https://existing.example.com",
        transport="http",
        provider_type="native",
        visibility="public",
        audit_status="approved",
        operation_status="active",
    )
    db_session.add(existing_provider)
    db_session.commit()

    # 创建有权限的用户
    user = _create_user(db_session, "dup-user", "dup-user@example.com", is_superuser=False)
    perm = UserPermissionService(db_session)
    perm.grant_permission(user.id, "submit_shared_provider")

    async def _fake_validate(_self, base_url: str, api_key: str, provider_type: str):
        return ProviderValidationResult(is_valid=True, error_message=None, metadata={})

    monkeypatch.setattr(
        "app.services.provider_validation_service.ProviderValidationService.validate_provider_config",
        _fake_validate,
        raising=False,
    )

    headers = jwt_auth_headers(str(user.id))
    resp = client.post(
        "/providers/submissions",
        headers=headers,
        json={
            "name": "Dup Submission",
            "provider_id": "dup-provider",
            "base_url": "https://dup.example.com",
            "provider_type": "native",
            "api_key": "sk-test-dup",
        },
    )

    assert resp.status_code == 400
    detail = resp.json().get("detail", {})
    assert "已存在" in (detail.get("message") or "")
    # 确认没有创建新的 Submission
    sub = db_session.execute(
        select(ProviderSubmission).where(ProviderSubmission.provider_id == "dup-provider")
    ).scalars().first()
    assert sub is None


def test_submit_private_provider_to_shared_pool_success(
    client,
    db_session,
    monkeypatch,
):
    # 创建普通用户并授予提交共享 Provider 权限
    user = _create_user(db_session, "normal-user", "normal@example.com", is_superuser=False)
    perm = UserPermissionService(db_session)
    perm.grant_permission(user.id, "submit_shared_provider")

    # 为该用户创建一个私有 Provider（包含上游密钥）
    create_payload = UserProviderCreateRequest(
        name="My Private Provider",
        base_url="https://api.example.com",
        api_key="sk-test-123",
        chat_completions_path="/v1/chat/completions",
    )
    provider: Provider = create_private_provider(db_session, user.id, create_payload)

    # 避免真实网络请求，mock ProviderValidationService.validate_provider_config
    async def _fake_validate(_self, base_url: str, api_key: str, provider_type: str):
        return ProviderValidationResult(
            is_valid=True,
            error_message=None,
            metadata={"model_count": 1, "base_url": base_url, "provider_type": provider_type},
        )

    monkeypatch.setattr(
        "app.services.provider_validation_service.ProviderValidationService.validate_provider_config",
        _fake_validate,
        raising=False,
    )

    headers = jwt_auth_headers(str(user.id))
    resp = client.post(
        f"/users/{user.id}/private-providers/{provider.provider_id}/submit-shared",
        headers=headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == str(user.id)
    assert data["provider_id"] == provider.provider_id
    assert data["approval_status"] == "pending"

    # 确认数据库中写入了一条提交记录
    submission = db_session.execute(
        select(ProviderSubmission).where(ProviderSubmission.provider_id == provider.provider_id)
    ).scalars().first()
    assert submission is not None
    assert submission.user_id == user.id


def test_submit_private_provider_to_shared_pool_requires_permission(
    client,
    db_session,
    monkeypatch,
):
    # 创建一个没有 submit_shared_provider 权限的普通用户
    user = _create_user(db_session, "no-perm-user", "no-perm@example.com", is_superuser=False)

    create_payload = UserProviderCreateRequest(
        name="My Private Provider",
        base_url="https://api.example.com",
        api_key="sk-test-123",
        chat_completions_path="/v1/chat/completions",
    )
    provider: Provider = create_private_provider(db_session, user.id, create_payload)

    # 即便 mock 了校验逻辑，由于权限不足，仍应在到达校验前就被拒绝
    async def _fake_validate(_self, base_url: str, api_key: str, provider_type: str):
        return ProviderValidationResult(
            is_valid=True,
            error_message=None,
            metadata={},
        )

    monkeypatch.setattr(
        "app.services.provider_validation_service.ProviderValidationService.validate_provider_config",
        _fake_validate,
        raising=False,
    )

    headers = jwt_auth_headers(str(user.id))
    resp = client.post(
        f"/users/{user.id}/private-providers/{provider.provider_id}/submit-shared",
        headers=headers,
    )

    assert resp.status_code == 403


def test_admin_list_submissions_uses_submission_router(client, db_session):
    """确保 /providers/submissions 命中投稿路由而不是 Provider 详情路由。"""

    # 创建一个超级管理员用户
    admin = _create_user(
        db_session,
        "admin-submissions",
        "admin-submissions@example.com",
        is_superuser=True,
    )

    # 为该管理员插入一条投稿记录
    submission = ProviderSubmission(
        user_id=admin.id,
        name="Shared Provider From Admin",
        provider_id="admin-provider-shared",
        base_url="https://api.example.com",
        provider_type="native",
        description="Admin submission",
        approval_status="pending",
    )
    db_session.add(submission)
    db_session.commit()
    db_session.refresh(submission)

    headers = jwt_auth_headers(str(admin.id))

    resp = client.get("/providers/submissions", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    # 应返回投稿列表（数组），包含我们刚创建的那条记录
    assert isinstance(data, list)
    ids = {item["id"] for item in data}
    assert str(submission.id) in ids


def test_submission_review_broadcasts_notification(client, db_session):
    admin = _create_user(
        db_session,
        "notify-admin",
        "notify-admin@example.com",
        is_superuser=True,
    )
    submitter = _create_user(
        db_session,
        "notify-user",
        "notify-user@example.com",
        is_superuser=False,
    )

    submission = create_submission(
        db_session,
        submitter.id,
        ProviderSubmissionRequest(
            name="Broadcast Provider",
            provider_id="broadcast-provider",
            base_url="https://broadcast.example.com",
            provider_type="native",
            api_key="sk-test-broadcast",
        ),
    )

    notifications_after_submit = db_session.execute(select(Notification)).scalars().all()
    assert len(notifications_after_submit) == 1
    assert notifications_after_submit[0].title == "共享提供商提交已创建"

    headers = jwt_auth_headers(str(admin.id))
    resp = client.put(
        f"/providers/submissions/{submission.id}/review",
        headers=headers,
        json={"approved": True, "review_notes": "ok"},
    )
    assert resp.status_code == 200

    db_session.expire_all()
    notifications_after_review = db_session.execute(select(Notification)).scalars().all()
    assert len(notifications_after_review) == 3
    titles = {n.title for n in notifications_after_review}
    assert "共享提供商审核通过" in titles
    broadcast = [n for n in notifications_after_review if n.target_type == "all"]
    assert len(broadcast) == 1
    assert submission.provider_id in (broadcast[0].content or "")


def test_submission_review_promotes_private_provider_to_public(client, db_session):
    admin = _create_user(
        db_session,
        "promote-admin",
        "promote-admin@example.com",
        is_superuser=True,
    )
    submitter = _create_user(
        db_session,
        "promote-user",
        "promote-user@example.com",
        is_superuser=False,
    )

    create_payload = UserProviderCreateRequest(
        name="Private Provider",
        base_url="https://private.example.com",
        api_key="sk-private-123",
        chat_completions_path="/v1/chat/completions",
    )
    provider = create_private_provider(db_session, submitter.id, create_payload)

    submission = create_submission(
        db_session,
        submitter.id,
        ProviderSubmissionRequest(
            name="Private Provider",
            provider_id=provider.provider_id,
            base_url="https://private.example.com",
            provider_type="native",
            api_key="sk-private-123",
        ),
    )

    assert provider.visibility == "private"
    headers = jwt_auth_headers(str(admin.id))
    resp = client.put(
        f"/providers/submissions/{submission.id}/review",
        headers=headers,
        json={"approved": True, "limit_qps": 5},
    )
    assert resp.status_code == 200

    db_session.refresh(provider)
    db_session.refresh(submission)

    assert provider.visibility == "public"
    assert provider.owner_id is None
    assert provider.audit_status == "approved"
    assert provider.max_qps == 5
    assert submission.approved_provider_uuid == provider.id
    # 仍然只有一条 Provider 记录
    providers = db_session.execute(
        select(Provider).where(Provider.provider_id == provider.provider_id)
    ).scalars().all()
    assert len(providers) == 1


def test_submission_review_invalidates_cache(monkeypatch, client, db_session):
    admin = _create_user(
        db_session,
        "cache-admin",
        "cache-admin@example.com",
        is_superuser=True,
    )
    submitter = _create_user(
        db_session,
        "cache-user",
        "cache-user@example.com",
        is_superuser=False,
    )

    submission = create_submission(
        db_session,
        submitter.id,
        ProviderSubmissionRequest(
            name="Cache Provider",
            provider_id="cache-provider",
            base_url="https://cache.example.com",
            provider_type="native",
            api_key="sk-cache-test",
        ),
    )

    called: dict[str, str] = {}

    async def _fake_invalidate(redis, provider_id: str):
        called["provider_id"] = provider_id

    monkeypatch.setattr(
        "app.api.v1.provider_submission_routes._invalidate_public_provider_cache",
        _fake_invalidate,
    )

    headers = jwt_auth_headers(str(admin.id))
    resp = client.put(
        f"/providers/submissions/{submission.id}/review",
        headers=headers,
        json={"approved": True},
    )
    assert resp.status_code == 200
    assert called.get("provider_id") == submission.provider_id


def test_submission_review_fails_when_provider_id_conflicts(client, db_session):
    admin = _create_user(
        db_session,
        "conflict-admin",
        "conflict-admin@example.com",
        is_superuser=True,
    )
    submitter = _create_user(
        db_session,
        "conflict-user",
        "conflict-user@example.com",
        is_superuser=False,
    )

    submission = create_submission(
        db_session,
        submitter.id,
        ProviderSubmissionRequest(
            name="Dup Provider Submission",
            provider_id="dup-provider",
            base_url="https://dup.example.com",
            provider_type="native",
            api_key="sk-test-dup",
        ),
    )

    # 提交创建后才出现同名 Provider，模拟审核阶段的冲突场景
    existing_provider = Provider(
        provider_id="dup-provider",
        name="Existing Provider",
        base_url="https://existing.example.com",
        transport="http",
        provider_type="native",
        visibility="public",
        audit_status="approved",
        operation_status="active",
    )
    db_session.add(existing_provider)
    db_session.commit()
    db_session.refresh(existing_provider)

    headers = jwt_auth_headers(str(admin.id))
    resp = client.put(
        f"/providers/submissions/{submission.id}/review",
        headers=headers,
        json={"approved": True},
    )

    assert resp.status_code == 400
    detail = resp.json().get("detail", {})
    assert "已存在" in (detail.get("message") or "")

    db_session.refresh(submission)
    assert submission.approval_status == "pending"
    assert submission.approved_provider_uuid is None
@pytest.fixture(autouse=True)
def _override_redis_dependency(client):
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    client.app.dependency_overrides[get_redis] = override_get_redis
    yield
    client.app.dependency_overrides.pop(get_redis, None)
