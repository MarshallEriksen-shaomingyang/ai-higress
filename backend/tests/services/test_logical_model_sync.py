from unittest.mock import AsyncMock

import pytest

import app.services.logical_model_sync as logical_sync
from app.schemas.logical_model import LogicalModel, PhysicalModel
from app.schemas.model import ModelCapability


def _logical_model(provider_id: str) -> LogicalModel:
    upstream = PhysicalModel(
        provider_id=provider_id,
        model_id="gpt-4",
        endpoint="https://api.example.com/v1/chat/completions",
        base_weight=2.0,
        region=None,
        max_qps=None,
        meta_hash=None,
        updated_at=1.0,
    )
    return LogicalModel(
        logical_id="gpt-4",
        display_name="gpt-4",
        description="desc",
        capabilities=[ModelCapability.CHAT],
        upstreams=[upstream],
        enabled=True,
        updated_at=1.0,
    )


@pytest.mark.asyncio
async def test_sync_logical_models_invalidates_dynamic_weights(monkeypatch):
    logical = _logical_model("primary")
    redis = object()
    sync_mock = AsyncMock()
    delete_mock = AsyncMock()
    list_mock = AsyncMock(return_value=[])
    invalidate_mock = AsyncMock()

    monkeypatch.setattr(
        logical_sync, "collect_logical_models", lambda **_: [logical]
    )
    monkeypatch.setattr(logical_sync, "sync_logical_models_to_redis", sync_mock)
    monkeypatch.setattr(logical_sync, "delete_logical_model", delete_mock)
    monkeypatch.setattr(logical_sync, "list_logical_models", list_mock)
    monkeypatch.setattr(
        logical_sync, "invalidate_provider_weights", invalidate_mock
    )

    await logical_sync.sync_logical_models(redis, provider_ids=["primary"])

    sync_mock.assert_awaited_once()
    delete_mock.assert_not_awaited()
    assert invalidate_mock.await_count == 1
    args, kwargs = invalidate_mock.await_args_list[0]
    assert args == (redis, logical.logical_id, ["primary"])
    assert kwargs == {}


@pytest.mark.asyncio
async def test_sync_logical_models_cleans_weights_for_stale_entries(monkeypatch):
    redis = object()
    sync_mock = AsyncMock()
    stale_logical = _logical_model("primary")
    list_mock = AsyncMock(return_value=[stale_logical])
    delete_mock = AsyncMock()
    invalidate_mock = AsyncMock()

    monkeypatch.setattr(
        logical_sync, "collect_logical_models", lambda **_: []
    )
    monkeypatch.setattr(logical_sync, "sync_logical_models_to_redis", sync_mock)
    monkeypatch.setattr(logical_sync, "delete_logical_model", delete_mock)
    monkeypatch.setattr(logical_sync, "list_logical_models", list_mock)
    monkeypatch.setattr(
        logical_sync, "invalidate_provider_weights", invalidate_mock
    )

    await logical_sync.sync_logical_models(redis, provider_ids=["primary"])

    sync_mock.assert_not_awaited()
    delete_mock.assert_awaited_once()
    invalidate_mock.assert_awaited_once()
    args, kwargs = invalidate_mock.await_args_list[0]
    assert args == (redis, stale_logical.logical_id)
    assert kwargs == {}
