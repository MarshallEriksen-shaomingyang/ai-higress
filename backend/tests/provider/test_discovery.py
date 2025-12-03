from typing import Any

import httpx
import pytest

from app.schemas import Model, ProviderConfig
from app.provider.discovery import (
    ensure_provider_models_cached,
    fetch_models_from_provider,
)
from app.provider.key_pool import reset_key_pool


class DummyRedis:
    """
    Minimal Redis replacement for discovery tests.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value


def _make_provider(**overrides: Any) -> ProviderConfig:
    data: dict[str, Any] = {
        "id": "mock",
        "name": "Mock Provider",
        "base_url": "https://api.mock.local",
        "api_key": "sk-test",  # pragma: allowlist secret
        "models_path": "/v1/models",
    }
    data.update(overrides)
    return ProviderConfig(**data)


@pytest.fixture(autouse=True)
def _reset_key_pool():
    reset_key_pool()
    yield
    reset_key_pool()


@pytest.mark.asyncio
async def test_fetch_models_from_provider_normalises_payload():
    provider = _make_provider()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/models")
        data = {
            "object": "list",
            "data": [
                {"id": "m1", "context_length": 4096, "capabilities": ["chat"]},
                {"id": "m2", "context_length": 8192, "capabilities": ["completion"]},
            ],
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        models: list[Model] = await fetch_models_from_provider(client, provider)

    assert len(models) == 2
    assert models[0].model_id == "m1"
    assert models[0].context_length == 4096
    assert models[1].model_id == "m2"
    assert models[1].context_length == 8192


@pytest.mark.asyncio
async def test_fetch_models_from_provider_uses_static_models():
    provider = _make_provider(
        static_models=[
            {"id": "manual-1", "context_length": 1024},
            {"id": "manual-2", "context_length": 2048},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - should not run
        raise AssertionError("HTTP call should be skipped when static_models is set")

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        models: list[Model] = await fetch_models_from_provider(client, provider)

    assert [m.model_id for m in models] == ["manual-1", "manual-2"]
    assert [m.context_length for m in models] == [1024, 2048]


@pytest.mark.asyncio
async def test_fetch_models_from_provider_falls_back_to_env_static_on_invalid_json(
    monkeypatch,
):
    provider = _make_provider()

    fallback_provider = _make_provider(
        static_models=[{"id": "env-manual-1", "context_length": 1234}]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/models")
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"<html>not json</html>",
        )

    monkeypatch.setattr(
        "app.provider.discovery.get_provider_config",
        lambda provider_id: fallback_provider if provider_id == provider.id else None,
    )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        models: list[Model] = await fetch_models_from_provider(client, provider)

    assert [m.model_id for m in models] == ["env-manual-1"]
    assert [m.context_length for m in models] == [1234]


@pytest.mark.asyncio
async def test_fetch_models_from_provider_raises_when_no_fallback(monkeypatch):
    provider = _make_provider()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/models")
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"*invalid-json*",
        )

    monkeypatch.setattr("app.provider.discovery.get_provider_config", lambda _: None)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError):
            await fetch_models_from_provider(client, provider)


@pytest.mark.asyncio
async def test_ensure_provider_models_cached_uses_redis_cache():
    provider = _make_provider()
    redis = DummyRedis()
    call_count = {"models": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["models"] += 1
        data = {
            "object": "list",
            "data": [
                {"id": "m1", "context_length": 4096, "capabilities": ["chat"]},
            ],
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        models_first = await ensure_provider_models_cached(client, redis, provider)
        models_second = await ensure_provider_models_cached(client, redis, provider)

    assert call_count["models"] == 1
    assert models_first == models_second
    assert len(models_first) == 1
    assert models_first[0]["model_id"] == "m1"
