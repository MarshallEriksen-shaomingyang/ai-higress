from typing import Any

import pytest

from app.routing.session_manager import (
    bind_session,
    delete_session,
    get_session,
    touch_session,
)


class DummyRedis:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value

    async def delete(self, key: str):
        self._data.pop(key, None)


@pytest.mark.asyncio
async def test_bind_get_touch_and_delete_session():
    redis = DummyRedis()

    # Initially no session
    sess = await get_session(redis, "conv1")
    assert sess is None

    # Bind new session
    created = await bind_session(
        redis,
        conversation_id="conv1",
        logical_model="gpt-4",
        provider_id="openai",
        model_id="gpt-4",
        ts=100.0,
    )
    assert created.conversation_id == "conv1"
    assert created.logical_model == "gpt-4"

    # Load again
    loaded = await get_session(redis, "conv1")
    assert loaded is not None
    assert loaded.provider_id == "openai"

    # Touch session
    updated = await touch_session(redis, "conv1", increment_messages=2)
    assert updated is not None
    assert updated.message_count == created.message_count + 2

    # Delete session
    deleted = await delete_session(redis, "conv1")
    assert deleted is True
    assert await get_session(redis, "conv1") is None

