import asyncio

import pytest

from app.provider.key_pool import (
    NoAvailableProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
    reset_key_pool,
)
from app.schemas import ProviderAPIKey, ProviderConfig


def _make_provider(provider_id: str = "multi") -> ProviderConfig:
    return ProviderConfig(
        id=provider_id,
        name="Multi Key Provider",
        base_url="https://api.multi.local",
        api_keys=[
            ProviderAPIKey(key="k1"),  # pragma: allowlist secret
            ProviderAPIKey(key="k2"),  # pragma: allowlist secret
        ],
    )


class InMemoryRedis:
    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = {}

    async def zadd(self, key: str, mapping: dict[str, float], nx: bool = False) -> int:
        zset = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if nx and member in zset:
                continue
            zset[member] = float(score)
            added += 1
        return added

    async def zscore(self, key: str, member: str):
        return self.zsets.get(key, {}).get(member)

    async def zincrby(self, key: str, amount: float, member: str) -> float:
        zset = self.zsets.setdefault(key, {})
        zset[member] = zset.get(member, 0.0) + float(amount)
        return zset[member]


@pytest.mark.asyncio
async def test_acquire_provider_key_skips_backoff_key(monkeypatch):
    provider = _make_provider("backoff")
    reset_key_pool(provider.id)

    first = await acquire_provider_key(provider, redis=None)
    record_key_failure(first, retryable=False, status_code=401)

    second = await acquire_provider_key(provider, redis=None)
    assert second.key != first.key

    reset_key_pool(provider.id)


@pytest.mark.asyncio
async def test_acquire_provider_key_raises_when_all_in_backoff(monkeypatch):
    provider = ProviderConfig(
        id="single",
        name="Single Key Provider",
        base_url="https://api.single.local",
        api_keys=[ProviderAPIKey(key="solo")],  # pragma: allowlist secret
    )
    reset_key_pool(provider.id)

    selection = await acquire_provider_key(provider, redis=None)
    record_key_failure(selection, retryable=False, status_code=401)

    with pytest.raises(NoAvailableProviderKey):
        await acquire_provider_key(provider, redis=None)

    reset_key_pool(provider.id)


@pytest.mark.asyncio
async def test_acquire_prefers_high_score_from_redis(monkeypatch):
    """
    高分 key 应优先被选中，Redis 只存哈希 + 分数。
    """

    from app.provider import key_pool

    provider_id = "prefer-redis"
    reset_key_pool(provider_id)
    # 使随机选择确定性：总是挑最大权重的候选。
    monkeypatch.setattr(
        key_pool.random,
        "choices",
        lambda seq, weights, k=1: [seq[weights.index(max(weights))]],
    )
    redis = InMemoryRedis()

    # 先用不均衡权重把 k2 选出来，累积成功分。
    provider_bias = ProviderConfig(
        id=provider_id,
        name="Prefer Provider",
        base_url="https://api.prefer.local",
        api_keys=[
            ProviderAPIKey(key="k1", weight=0.1),  # pragma: allowlist secret
            ProviderAPIKey(key="k2", weight=10),  # pragma: allowlist secret
        ],
    )
    first = await acquire_provider_key(provider_bias, redis=redis)
    assert first.key == "k2"
    record_key_success(first, redis=redis)
    await asyncio.sleep(0)

    # 重置本地状态，使用均衡权重；应当仍然优选 k2（Redis 分数更高）。
    reset_key_pool(provider_id)
    provider_balanced = ProviderConfig(
        id=provider_id,
        name="Prefer Provider",
        base_url="https://api.prefer.local",
        api_keys=[
            ProviderAPIKey(key="k1"),  # pragma: allowlist secret
            ProviderAPIKey(key="k2"),  # pragma: allowlist secret
        ],
    )
    second = await acquire_provider_key(provider_balanced, redis=redis)
    assert second.key == "k2"

    reset_key_pool(provider_id)
