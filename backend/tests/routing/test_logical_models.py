import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.deps import get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.routes import create_app
from app.schemas import LogicalModel, ModelCapability, PhysicalModel
from app.storage.redis_service import LOGICAL_MODEL_KEY_TEMPLATE
from tests.utils import install_inmemory_db


class DummyRedis:
    """
    Minimal Redis replacement that supports the subset of commands used
    by logical_model_routes and redis_service for logical models.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value

    async def keys(self, pattern: str):
        # Very small emulation of KEYS with a suffix wildcard.
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._data.keys() if k.startswith(prefix)]
        return [k for k in self._data.keys() if k == pattern]

    async def delete(self, key: str):
        self._data.pop(key, None)


fake_redis = DummyRedis()


async def override_get_redis():
    return fake_redis


def make_override_require_jwt_token(user_id: str) -> Callable:
    async def override_require_jwt_token() -> AuthenticatedUser:
        # 简化依赖：测试路由行为时，不关心具体用户信息
        return AuthenticatedUser(
            id=user_id,
            username="test",
            email="test@example.com",
            is_superuser=True,
            is_active=True,
            display_name=None,
            avatar=None,
        )
    return override_require_jwt_token


def _store_logical_model(logical: LogicalModel) -> None:
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical.logical_id)
    fake_redis._data[key] = json.dumps(logical.model_dump(), ensure_ascii=False)


def _make_sample_models() -> list[LogicalModel]:
    logical1 = LogicalModel(
        logical_id="gpt-4",
        display_name="GPT-4",
        description="Main GPT-4 logical model",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id="openai",
                model_id="gpt-4",
                endpoint="https://api.openai.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=1704067200.0,
            )
        ],
        enabled=True,
        updated_at=1704067200.0,
    )
    logical2 = LogicalModel(
        logical_id="gpt-4-mini",
        display_name="GPT-4 Mini",
        description="Smaller GPT-4 variant",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id="openai",
                model_id="gpt-4-mini",
                endpoint="https://api.openai.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=1704067200.0,
            )
        ],
        enabled=True,
        updated_at=1704067200.0,
    )
    return [logical1, logical2]


def test_logical_model_routes_list_and_get():
    from app.models import Provider, User

    app = create_app()
    # logical_model_routes is already included by create_app via app.include_router

    SessionLocal = install_inmemory_db(app)
    app.dependency_overrides[get_redis] = override_get_redis

    # 获取测试用户的 ID
    with SessionLocal() as session:
        user = session.query(User).filter_by(username="admin").first()
        user_id = str(user.id)

    # 使用真实的用户 ID 来 override JWT token
    app.dependency_overrides[require_jwt_token] = make_override_require_jwt_token(user_id)

    # Clear Redis before seeding
    fake_redis._data.clear()

    # 创建 Provider，使得用户有权限访问
    with SessionLocal() as session:
        provider1 = Provider(
            provider_id="openai",
            name="OpenAI",
            base_url="https://api.openai.com/v1",
            transport="http",
            provider_type="native",
            weight=1.0,
            status="healthy",
            visibility="public",
        )
        session.add(provider1)
        session.commit()

    # Seed Redis with two logical models.
    for lm in _make_sample_models():
        _store_logical_model(lm)

    with TestClient(app=app, base_url="http://test") as client:
        resp = client.get("/logical-models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        ids = {m["logical_id"] for m in data["models"]}
        assert ids == {"gpt-4", "gpt-4-mini"}

        resp_one = client.get("/logical-models/gpt-4")
        assert resp_one.status_code == 200
        one = resp_one.json()
        assert one["logical_id"] == "gpt-4"
        assert one["display_name"] == "GPT-4"

        # Unknown logical model -> 404
        resp_missing = client.get("/logical-models/unknown")
        assert resp_missing.status_code == 404


def test_logical_model_routes_upstreams():
    from app.models import Provider, User

    app = create_app()
    SessionLocal = install_inmemory_db(app)
    app.dependency_overrides[get_redis] = override_get_redis

    # 获取测试用户的 ID
    with SessionLocal() as session:
        user = session.query(User).filter_by(username="admin").first()
        user_id = str(user.id)

    # 使用真实的用户 ID 来 override JWT token
    app.dependency_overrides[require_jwt_token] = make_override_require_jwt_token(user_id)

    fake_redis._data.clear()
    logical = _make_sample_models()[0]
    _store_logical_model(logical)

    # 创建一个 Provider，使得用户有权限访问
    with SessionLocal() as session:
        provider = Provider(
            provider_id="openai",
            name="OpenAI",
            base_url="https://api.openai.com/v1",
            transport="http",
            provider_type="native",
            weight=1.0,
            status="healthy",
            visibility="public",
        )
        session.add(provider)
        session.commit()

    with TestClient(app=app, base_url="http://test") as client:
        resp = client.get("/logical-models/gpt-4/upstreams")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["upstreams"], list)
        assert len(data["upstreams"]) == 1
        assert data["upstreams"][0]["provider_id"] == "openai"
