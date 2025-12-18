from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db, get_redis
from app.models import Base, User
from app.routes import create_app
from tests.utils import InMemoryRedis, auth_headers, jwt_auth_headers, seed_user_and_key


def _jwt_auth_headers(user_id: str) -> dict[str, str]:
    """生成 JWT 认证头（用于用户管理路由）"""
    return jwt_auth_headers(user_id)


@pytest.fixture()
def client_with_db() -> tuple[TestClient, sessionmaker[Session], str, InMemoryRedis]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = TestingSessionLocal()
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

    # 创建测试用的超级用户
    admin_user = None
    with TestingSessionLocal() as session:
        admin_user, _ = seed_user_and_key(session, token_plain="timeline")

    with TestClient(app, base_url="http://test") as client:
        # 返回客户端、Session 工厂、管理员用户 ID 以及用于检查会话状态的 InMemoryRedis
        yield client, TestingSessionLocal, str(admin_user.id), fake_redis

    Base.metadata.drop_all(bind=engine)


def test_register_user_persists_record(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "Secret123!",
        "display_name": "Alice",
        "avatar": "https://img.local/alice.png",
    }

    resp = client.post("/users", json=payload, headers=_jwt_auth_headers(admin_id))

    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == payload["username"]
    assert data["email"] == payload["email"]

    with session_factory() as session:
        saved = session.execute(
            select(User).where(User.username == payload["username"])
        ).scalars().first()
        assert saved is not None
        assert saved.hashed_password != payload["password"]


def test_register_user_duplicate_username_returns_400(client_with_db):
    client, _, admin_id, _redis = client_with_db
    base_payload = {
        "username": "bob",
        "email": "bob@example.com",
        "password": "Secret123!",
    }
    resp = client.post("/users", json=base_payload, headers=_jwt_auth_headers(admin_id))
    assert resp.status_code == 201

    resp_dup = client.post(
        "/users",
        json={**base_payload, "email": "bob-2@example.com"},
        headers=_jwt_auth_headers(admin_id),
    )
    assert resp_dup.status_code == 400
    assert resp_dup.json()["detail"]["message"] == "用户名已存在"


def test_update_user_changes_profile_and_password(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db
    payload = {
        "username": "charlie",
        "email": "charlie@example.com",
        "password": "Secret123!",
    }
    resp = client.post("/users", json=payload, headers=_jwt_auth_headers(admin_id))
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    with session_factory() as session:
        before_hash = session.get(User, uuid.UUID(user_id)).hashed_password

    update_payload = {
        "display_name": "Charlie 2",
        "avatar": "https://img.local/charlie.png",
        "password": "NewSecret456!",
    }
    resp_update = client.put(
        f"/users/{user_id}",
        json=update_payload,
        headers=_jwt_auth_headers(admin_id),
    )
    assert resp_update.status_code == 200
    data = resp_update.json()
    assert data["display_name"] == update_payload["display_name"]
    assert data["avatar"] == update_payload["avatar"]

    with session_factory() as session:
        updated = session.get(User, uuid.UUID(user_id))
        assert updated is not None
        assert updated.display_name == update_payload["display_name"]
        assert updated.hashed_password != before_hash


def test_update_missing_user_returns_404(client_with_db):
    client, _, admin_id, _redis = client_with_db
    resp = client.put(
        "/users/00000000-0000-0000-0000-000000000000",
        json={"display_name": "n/a"},
        headers=_jwt_auth_headers(admin_id),
    )
    assert resp.status_code == 404


def test_superuser_can_ban_user_and_revoke_access(client_with_db):
    client, _, admin_id, _redis = client_with_db

    create_payload = {
        "username": "diana",
        "email": "diana@example.com",
        "password": "Secret123!",
    }
    resp_user = client.post("/users", json=create_payload, headers=_jwt_auth_headers(admin_id))
    assert resp_user.status_code == 201
    user_id = resp_user.json()["id"]

    resp_key = client.post(
        f"/users/{user_id}/api-keys",
        json={"name": "diana-key", "expiry": "never"},
        headers=_jwt_auth_headers(admin_id),
    )
    assert resp_key.status_code == 201
    # 使用新创建用户的 JWT token
    user_headers = _jwt_auth_headers(user_id)

    resp_cache = client.put(
        f"/users/{user_id}",
        json={"display_name": "Diana"},
        headers=user_headers,
    )
    assert resp_cache.status_code == 200

    ban_resp = client.put(
        f"/users/{user_id}/status",
        json={"is_active": False},
        headers=_jwt_auth_headers(admin_id),
    )
    assert ban_resp.status_code == 200
    assert ban_resp.json()["is_active"] is False

    resp_after_ban = client.put(
        f"/users/{user_id}",
        json={"display_name": "Diana 2"},
        headers=user_headers,
    )
    assert resp_after_ban.status_code == 403
    assert resp_after_ban.json()["detail"] == "User account is disabled"


def test_ban_user_also_revokes_jwt_sessions_in_redis(client_with_db):
    """
    禁用用户时，除了数据库标记 is_active=False，还应清理其在 Redis 中登记的会话信息。
    这里通过直接检查 InMemoryRedis 中的会话 key 是否被删除来验证。
    """
    import asyncio

    client, _, admin_id, redis = client_with_db

    # 1. 创建一个普通用户
    create_payload = {
        "username": "frank",
        "email": "frank@example.com",
        "password": "Secret123!",
    }
    resp_user = client.post("/users", json=create_payload, headers=_jwt_auth_headers(admin_id))
    assert resp_user.status_code == 201
    user_id = resp_user.json()["id"]

    # 2. 通过 /auth/login 登录，触发 TokenRedisService.store_* 将会话写入 Redis
    login_resp = client.post(
        "/auth/login",
        json={"email": create_payload["email"], "password": create_payload["password"]},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]

    # 确认会话 key 已经写入 Redis
    sessions_key = f"auth:user:{user_id}:sessions"
    raw_before = asyncio.run(redis.get(sessions_key))
    assert raw_before is not None

    # 3. 管理员禁用该用户
    ban_resp = client.put(
        f"/users/{user_id}/status",
        json={"is_active": False},
        headers=_jwt_auth_headers(admin_id),
    )
    assert ban_resp.status_code == 200
    assert ban_resp.json()["is_active"] is False

    # 4. 禁用后，会话 key 应被删除，视为所有 JWT 会话已被撤销
    raw_after = asyncio.run(redis.get(sessions_key))
    assert raw_after is None

    # 同一个 access_token 再访问受保护接口，应不再被视为有效会话
    user_headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = client.get("/auth/me", headers=user_headers)
    assert me_resp.status_code in (401, 403)


def test_non_superuser_cannot_ban_user(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db

    target_payload = {
        "username": "eve",
        "email": "eve@example.com",
        "password": "Secret123!",
    }
    resp_user = client.post("/users", json=target_payload, headers=_jwt_auth_headers(admin_id))
    assert resp_user.status_code == 201
    target_id = resp_user.json()["id"]

    with session_factory() as session:
        worker_user, _ = seed_user_and_key(
            session,
            token_plain="worker",
            username="worker",
            email="worker@example.com",
            is_superuser=False,
        )

    worker_headers = _jwt_auth_headers(str(worker_user.id))
    resp_ban = client.put(
        f"/users/{target_id}/status",
        json={"is_active": False},
        headers=worker_headers,
    )

    assert resp_ban.status_code == 403


def test_admin_can_list_all_users(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db

    # 先通过 /users 创建一个普通用户，确保列表中有多条记录
    payload = {
        "username": "list-user",
        "email": "list-user@example.com",
        "password": "Secret123!",
    }
    resp = client.post("/users", json=payload, headers=_jwt_auth_headers(admin_id))
    assert resp.status_code == 201
    created_user_id = resp.json()["id"]

    # 使用管理员身份获取用户列表
    resp_list = client.get("/admin/users", headers=_jwt_auth_headers(admin_id))
    assert resp_list.status_code == 200

    data = resp_list.json()
    assert isinstance(data, list)
    ids = {item["id"] for item in data}

    # 列表中应包含管理员和新创建的普通用户
    assert admin_id in ids
    assert created_user_id in ids

    # 校验返回结构中包含角色与权限标记字段，便于前端展示
    sample = next(item for item in data if item["id"] == created_user_id)
    assert "role_codes" in sample
    assert isinstance(sample["role_codes"], list)
    assert "permission_flags" in sample
    assert isinstance(sample["permission_flags"], list)
    assert "credit_auto_topup" in sample
    assert sample["credit_auto_topup"] is None

    # 配置自动充值后，列表应能直接返回该用户的规则信息（用于前端标记已配置/已启用/已停用）
    resp_config = client.put(
        f"/v1/credits/admin/users/{created_user_id}/auto-topup",
        json={
            "min_balance_threshold": 100,
            "target_balance": 200,
            "is_active": True,
        },
        headers=_jwt_auth_headers(admin_id),
    )
    assert resp_config.status_code == 200

    resp_list_after = client.get("/admin/users", headers=_jwt_auth_headers(admin_id))
    assert resp_list_after.status_code == 200
    data_after = resp_list_after.json()
    sample_after = next(item for item in data_after if item["id"] == created_user_id)
    assert sample_after["credit_auto_topup"] is not None
    assert sample_after["credit_auto_topup"]["min_balance_threshold"] == 100
    assert sample_after["credit_auto_topup"]["target_balance"] == 200
    assert sample_after["credit_auto_topup"]["is_active"] is True


def test_non_superuser_cannot_list_users(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db

    # 新建一个非超级用户
    with session_factory() as session:
        worker_user, _ = seed_user_and_key(
            session,
            token_plain="worker-list",
            username="worker-list",
            email="worker-list@example.com",
            is_superuser=False,
        )

    worker_headers = _jwt_auth_headers(str(worker_user.id))
    resp = client.get("/admin/users", headers=worker_headers)

    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["message"] == "需要管理员权限"


def test_search_users_by_keyword(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db
    payload = {
        "username": "share-target",
        "email": "share-target@example.com",
        "password": "Secret123!",
    }
    resp = client.post("/users", json=payload, headers=_jwt_auth_headers(admin_id))
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    headers = _jwt_auth_headers(user_id)
    resp_search = client.get("/users/search", params={"q": "share"}, headers=headers)
    assert resp_search.status_code == 200
    data = resp_search.json()
    assert any(item["email"] == payload["email"] for item in data)


def test_search_users_by_ids(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db
    ids: list[str] = []
    for suffix in ("alpha", "beta"):
        payload = {
            "username": f"user-{suffix}",
            "email": f"user-{suffix}@example.com",
            "password": "Secret123!",
        }
        resp = client.post("/users", json=payload, headers=_jwt_auth_headers(admin_id))
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    resp_search = client.get(
        "/users/search",
        params=[("ids", ids[0]), ("ids", ids[1])],
        headers=_jwt_auth_headers(admin_id),
    )
    assert resp_search.status_code == 200
    data = resp_search.json()
    returned = {item["id"] for item in data}
    assert set(ids).issubset(returned)


def test_search_users_requires_params(client_with_db):
    client, session_factory, admin_id, _redis = client_with_db
    resp = client.get("/users/search", headers=_jwt_auth_headers(admin_id))
    assert resp.status_code == 400
    assert resp.json()["detail"] == "请输入关键字或提供用户 ID"


def test_upload_my_avatar_stores_key_and_exposes_url(client_with_db):
    """
    当前用户通过 /users/me/avatar 上传头像时：
    - 数据库中只保存相对 key（不包含完整 URL 前缀）；
    - 对外返回的 avatar 字段是可直接访问的 URL，默认形如 /media/avatars/<user_id>/<file>；
    - 对应的本地文件实际写入 AVATAR_LOCAL_DIR。
    """

    from app.settings import settings
    from app.services.avatar_service import get_avatar_file_path

    client, session_factory, admin_id, _redis = client_with_db

    # 先创建一个普通用户
    create_payload = {
        "username": "avatar-user",
        "email": "avatar-user@example.com",
        "password": "Secret123!",
    }
    resp_user = client.post("/users", json=create_payload, headers=_jwt_auth_headers(admin_id))
    assert resp_user.status_code == 201
    user_id = resp_user.json()["id"]

    # 使用该用户身份上传头像
    user_headers = _jwt_auth_headers(user_id)
    files = {
        "file": ("avatar.png", b"\x89PNG\r\n\x1a\nfake-image-data", "image/png"),
    }
    resp_upload = client.post("/users/me/avatar", files=files, headers=user_headers)
    assert resp_upload.status_code == 200
    data = resp_upload.json()

    # 返回的 avatar 字段应为可访问 URL，且包含用户 ID
    assert data["avatar"] is not None
    local_path = settings.avatar_local_base_url.rstrip("/")
    request_base = str(client.base_url).rstrip("/")
    api_base = settings.gateway_api_base_url.rstrip("/")
    assert data["avatar"].startswith(f"{request_base}{local_path}/")
    # 当请求基址与默认配置不同，也应优先使用实际访问域名
    assert not data["avatar"].startswith(f"{api_base}{local_path}/")
    assert user_id in data["avatar"]

    # 数据库中仅保存 key，而非完整 URL
    with session_factory() as session:
        stored = session.get(User, uuid.UUID(user_id))
        assert stored is not None
        assert stored.avatar is not None
        assert not stored.avatar.startswith("http")
        # 数据库存储的是 key，不带完整 URL 前缀
        assert not stored.avatar.startswith(local_path)

        # 对应的本地文件应存在于头像存储目录
        avatar_path = get_avatar_file_path(stored.avatar)
        assert avatar_path.exists()
