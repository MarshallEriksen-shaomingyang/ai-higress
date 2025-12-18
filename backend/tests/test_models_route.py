from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from app.deps import get_redis
from app.model_cache import MODELS_CACHE_KEY
from app.models import Provider, ProviderModel
from app.routes import create_app
from app.services.chat_routing_service import _get_or_fetch_models  # noqa: F401
from tests.utils import InMemoryRedis, auth_headers, install_inmemory_db


def _setup_app():
    app = create_app()
    session_factory = install_inmemory_db(app)
    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    return app, session_factory, fake_redis


def test_models_route_returns_cached_payload():
    app, _, fake_redis = _setup_app()
    cached = {"object": "list", "data": [{"id": "cached-model"}]}
    asyncio.run(fake_redis.set(MODELS_CACHE_KEY, json.dumps(cached)))

    with TestClient(app, base_url="http://test") as client:
        resp = client.get("/models", headers=auth_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == "cached-model"


def test_models_route_falls_back_to_database():
    app, session_factory, fake_redis = _setup_app()

    with session_factory() as session:
        provider = Provider(
            provider_id="openai",
            name="OpenAI",
            base_url="https://api.example.com",
            transport="http",
            weight=1.0,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="gpt-4",
                family="gpt",
                display_name="GPT-4",
                context_length=8192,
                capabilities=["chat"],
            )
        )
        session.commit()

    with TestClient(app, base_url="http://test") as client:
        resp = client.get("/models", headers=auth_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == "gpt-4"

    cached_payload = asyncio.run(fake_redis.get(MODELS_CACHE_KEY))
    assert cached_payload is not None


def test_models_route_excludes_disabled_models_from_database():
    app, session_factory, _fake_redis = _setup_app()

    with session_factory() as session:
        provider = Provider(
            provider_id="openai",
            name="OpenAI",
            base_url="https://api.example.com",
            transport="http",
            weight=1.0,
        )
        session.add(provider)
        session.flush()
        session.add_all(
            [
                ProviderModel(
                    provider_id=provider.id,
                    model_id="gpt-enabled",
                    family="gpt",
                    display_name="GPT Enabled",
                    context_length=8192,
                    capabilities=["chat"],
                    disabled=False,
                ),
                ProviderModel(
                    provider_id=provider.id,
                    model_id="gpt-disabled",
                    family="gpt",
                    display_name="GPT Disabled",
                    context_length=8192,
                    capabilities=["chat"],
                    disabled=True,
                ),
            ]
        )
        session.commit()

    with TestClient(app, base_url="http://test") as client:
        resp = client.get("/models", headers=auth_headers())
        assert resp.status_code == 200
        body = resp.json()
        ids = [item["id"] for item in body.get("data", [])]
        assert "gpt-enabled" in ids
        assert "gpt-disabled" not in ids
