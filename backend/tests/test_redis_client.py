from __future__ import annotations

import datetime as dt
import asyncio
import json

import pytest

import app.redis_client as redis_client
from app.redis_client import redis_set_json


class DummyRedis:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, int | None]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = (value, ex)


@pytest.mark.asyncio
async def test_redis_set_json_serialises_datetime() -> None:
    redis = DummyRedis()
    payload = {
        "ts": dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
        "nested": {"value": 1},
    }

    await redis_set_json(redis, "test:key", payload, ttl_seconds=30)

    stored_value, ttl = redis._data["test:key"]
    decoded = json.loads(stored_value)
    assert decoded["ts"] == "2024-01-01T00:00:00+00:00"
    assert decoded["nested"] == {"value": 1}
    assert ttl == 30


class _DummyPool:
    def __init__(self) -> None:
        self.disconnected = False

    async def disconnect(self, _inuse_connections: bool = True) -> None:
        self.disconnected = True


class DummyRedisWithClose:
    def __init__(self) -> None:
        self.closed = False
        self.connection_pool = _DummyPool()

    async def close(self) -> None:
        self.closed = True


class DummyRedisWithAclose:
    def __init__(self) -> None:
        self.closed_by: str | None = None
        self.connection_pool = _DummyPool()

    async def aclose(self) -> None:
        self.closed_by = "aclose"

    async def close(self) -> None:
        raise AssertionError("close() should not be called when aclose() exists")


@pytest.mark.asyncio
async def test_close_redis_client_for_current_loop_closes_and_unsets() -> None:
    loop = asyncio.get_running_loop()
    dummy = DummyRedisWithClose()
    clients_by_loop = getattr(redis_client, "_redis_clients_by_loop")
    clients_by_loop[loop] = dummy

    await redis_client.close_redis_client_for_current_loop()

    assert dummy.closed is True
    assert dummy.connection_pool.disconnected is True
    assert loop not in clients_by_loop


@pytest.mark.asyncio
async def test_close_redis_client_prefers_aclose() -> None:
    dummy = DummyRedisWithAclose()
    await redis_client.close_redis_client(dummy)
    assert dummy.closed_by == "aclose"
    assert dummy.connection_pool.disconnected is True
