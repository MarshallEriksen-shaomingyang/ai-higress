import json
from typing import Any

from fastapi.testclient import TestClient

from app.deps import get_redis
from app.schemas import LogicalModel, ModelCapability, PhysicalModel
from app.routes import create_app
from app.storage.redis_service import LOGICAL_MODEL_KEY_TEMPLATE
from tests.utils import auth_headers, install_inmemory_db


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
        upstreams=[],
        enabled=True,
        updated_at=1704067200.0,
    )
    return [logical1, logical2]


def test_logical_model_routes_list_and_get():
    app = create_app()
    # logical_model_routes is already included by create_app via app.include_router

    app.dependency_overrides[get_redis] = override_get_redis
    install_inmemory_db(app)

    # Seed Redis with two logical models.
    for lm in _make_sample_models():
        _store_logical_model(lm)

    with TestClient(app=app, base_url="http://test") as client:
        headers = auth_headers()

        resp = client.get("/logical-models", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        ids = {m["logical_id"] for m in data["models"]}
        assert ids == {"gpt-4", "gpt-4-mini"}

        resp_one = client.get("/logical-models/gpt-4", headers=headers)
        assert resp_one.status_code == 200
        one = resp_one.json()
        assert one["logical_id"] == "gpt-4"
        assert one["display_name"] == "GPT-4"

        # Unknown logical model -> 404
        resp_missing = client.get("/logical-models/unknown", headers=headers)
        assert resp_missing.status_code == 404


def test_logical_model_routes_upstreams():
    app = create_app()
    app.dependency_overrides[get_redis] = override_get_redis
    install_inmemory_db(app)

    fake_redis._data.clear()
    logical = _make_sample_models()[0]
    _store_logical_model(logical)

    with TestClient(app=app, base_url="http://test") as client:
        headers = auth_headers()
        resp = client.get("/logical-models/gpt-4/upstreams", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["upstreams"], list)
        assert len(data["upstreams"]) == 1
        assert data["upstreams"][0]["provider_id"] == "openai"
