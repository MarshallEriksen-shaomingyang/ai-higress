import pytest

from app.routing.provider_weight import (
    adjust_provider_weight,
    invalidate_provider_weights,
    load_dynamic_weights,
)
from app.schemas import PhysicalModel


class FakeRedis:
    def __init__(self):
        self._zsets = {}

    def _get(self, key):
        return self._zsets.setdefault(key, {})

    async def delete(self, key):
        return 1 if self._zsets.pop(key, None) is not None else 0

    async def zadd(self, key, mapping, nx: bool = False):
        zset = self._get(key)
        for member, score in mapping.items():
            if nx and member in zset:
                continue
            zset[member] = float(score)

    async def zcard(self, key):
        return len(self._zsets.get(key, {}))

    async def zmscore(self, key, members):
        zset = self._get(key)
        return [zset.get(member) for member in members]

    async def zrem(self, key, *members):
        zset = self._zsets.get(key)
        if not zset:
            return 0
        removed = 0
        for member in members:
            if member in zset:
                removed += 1
                del zset[member]
        if not zset:
            self._zsets.pop(key, None)
        return removed

    async def zincrby(self, key, delta, member):
        zset = self._get(key)
        zset[member] = zset.get(member, 0.0) + float(delta)
        return zset[member]


def _upstream(provider_id: str, weight: float) -> PhysicalModel:
    return PhysicalModel(
        provider_id=provider_id,
        model_id="gpt-4",
        endpoint="https://api.example.com/v1/chat/completions",
        base_weight=weight,
        region=None,
        max_qps=None,
        meta_hash=None,
        updated_at=1.0,
    )


@pytest.mark.asyncio
async def test_load_dynamic_weights_seeds_defaults():
    redis = FakeRedis()
    upstreams = [_upstream("primary", 2.0), _upstream("backup", 1.0)]

    weights = await load_dynamic_weights(redis, "gpt-4", upstreams)

    assert weights["primary"] == pytest.approx(2.0)
    assert weights["backup"] == pytest.approx(1.0)

    stored = await redis.zmscore(
        "routing:gpt-4:provider_weights", ["primary", "backup"]
    )
    assert stored == [2.0, 1.0]


@pytest.mark.asyncio
async def test_adjust_provider_weight_respects_clamps():
    redis = FakeRedis()
    logical_model = "gpt-4"
    upstreams = [_upstream("primary", 2.0)]
    await load_dynamic_weights(redis, logical_model, upstreams)
    key = f"routing:{logical_model}:provider_weights"

    # Large positive bump clamps to max factor.
    await adjust_provider_weight(
        redis, logical_model, "primary", base_weight=2.0, delta=20.0
    )
    stored = await redis.zmscore(key, ["primary"])
    assert stored[0] == pytest.approx(6.0)  # 2.0 * _MAX_FACTOR

    # Large negative bump clamps to min factor.
    await adjust_provider_weight(
        redis, logical_model, "primary", base_weight=2.0, delta=-100.0
    )
    stored = await redis.zmscore(key, ["primary"])
    assert stored[0] == pytest.approx(0.4)  # 2.0 * _MIN_FACTOR


@pytest.mark.asyncio
async def test_invalidate_provider_weights_supports_partial_and_full_reset():
    redis = FakeRedis()
    logical_model = "gpt-4"
    upstreams = [
        _upstream("primary", 2.0),
        _upstream("backup", 1.0),
    ]
    await load_dynamic_weights(redis, logical_model, upstreams)
    key = f"routing:{logical_model}:provider_weights"

    await invalidate_provider_weights(redis, logical_model, ["primary"])
    stored = await redis.zmscore(key, ["primary", "backup"])
    assert stored == [None, 1.0]

    await invalidate_provider_weights(redis, logical_model)
    stored_after = await redis.zmscore(key, ["backup"])
    assert stored_after == [None]
