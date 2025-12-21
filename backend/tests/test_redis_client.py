from __future__ import annotations

import datetime as dt
import json

import pytest

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
