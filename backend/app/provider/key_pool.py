"""
Weighted API key selection and backoff for providers with multiple keys.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import random
import time
from dataclasses import dataclass

from redis.asyncio import Redis

from app.logging_config import logger
from app.schemas import ProviderConfig
from app.settings import settings


@dataclass
class ProviderKeyState:
    key: str
    label: str
    weight: float
    max_qps: int | None
    fail_count: int = 0
    backoff_until: float = 0.0
    last_used_at: float = 0.0


@dataclass
class SelectedProviderKey:
    provider_id: str
    key: str
    label: str
    state: ProviderKeyState


class NoAvailableProviderKey(Exception):
    """
    Raised when no healthy/available key can be selected for a provider.
    """


_KEY_STATES: dict[str, dict[str, ProviderKeyState]] = {}
_LOCKS: dict[str, asyncio.Lock] = {}
_PREFERENCE_BASE = 1.0
_PREFERENCE_MIN = 0.1
_PREFERENCE_MAX = 10.0
_PREFERENCE_SUCCESS_DELTA = 0.5
_PREFERENCE_RETRYABLE_FAILURE_DELTA = -1.0
_PREFERENCE_FATAL_DELTA = -2.0
_PREFERENCE_AUTH_FAILURE_DELTA = -3.0
_PREFERENCE_GROUP_TOLERANCE = 0.05
_PREFERENCE_KEY_PREFIX = "provider:{provider_id}:key_scores"


def _get_lock(provider_id: str) -> asyncio.Lock:
    if provider_id not in _LOCKS:
        _LOCKS[provider_id] = asyncio.Lock()
    return _LOCKS[provider_id]


def _mask_label(raw_key: str, explicit: str | None, idx: int) -> str:
    if explicit:
        return explicit
    tail = raw_key[-4:] if raw_key else "xxxx"
    return f"key{idx + 1}-***{tail}"


def _preference_redis_key(provider_id: str) -> str:
    return _PREFERENCE_KEY_PREFIX.format(provider_id=provider_id)


def _hash_provider_key(provider_id: str, raw_key: str) -> str:
    secret = settings.secret_key.encode("utf-8")
    msg = f"{provider_id}:{raw_key}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _ensure_states(provider: ProviderConfig) -> list[ProviderKeyState]:
    """
    Initialise per-provider key state from ProviderConfig.
    """
    pool = _KEY_STATES.setdefault(provider.id, {})
    keys = provider.get_api_keys()
    if not keys:
        raise NoAvailableProviderKey(f"Provider {provider.id} has no configured keys")

    for idx, entry in enumerate(keys):
        label = _mask_label(entry.key, entry.label, idx)
        if entry.key not in pool:
            pool[entry.key] = ProviderKeyState(
                key=entry.key,
                label=label,
                weight=entry.weight,
                max_qps=entry.max_qps,
            )
        else:
            # Keep existing backoff state but refresh metadata.
            pool_entry = pool[entry.key]
            pool_entry.label = label
            pool_entry.weight = entry.weight
            pool_entry.max_qps = entry.max_qps

    # Drop any state entries no longer present in config.
    valid_keys = {entry.key for entry in keys}
    for stale_key in list(pool.keys()):
        if stale_key not in valid_keys:
            pool.pop(stale_key, None)

    return list(pool.values())


async def _reserve_qps(redis: Redis | None, provider_id: str, state: ProviderKeyState) -> bool:
    if redis is None or state.max_qps is None:
        return True
    bucket = f"provider:{provider_id}:key:{state.label}:qps:{int(time.time())}"
    count = await redis.incr(bucket)
    if count == 1:
        await redis.expire(bucket, 1)
    if count > state.max_qps:
        await redis.expire(bucket, 1)
        return False
    return True


async def _load_preference_scores(
    redis: Redis | None, provider_id: str, states: list[ProviderKeyState]
) -> dict[str, float]:
    """
    Fetch or initialise preference scores for candidate keys.
    Redis 中仅存储 HMAC 哈希，不存明文。
    """
    if redis is None:
        return {}

    zset_key = _preference_redis_key(provider_id)
    scores: dict[str, float] = {}
    for state in states:
        member = _hash_provider_key(provider_id, state.key)
        try:
            await redis.zadd(zset_key, {member: _PREFERENCE_BASE}, nx=True)
            score = await redis.zscore(zset_key, member)
        except Exception as exc:  # pragma: no cover - 防止偏好存取影响主流程
            logger.debug(
                "provider=%s preference score lookup failed: %s", provider_id, exc
            )
            return {}
        if score is not None:
            scores[member] = float(score)
    return scores


async def _adjust_preference_score(
    redis: Redis | None, selection: SelectedProviderKey, delta: float
) -> None:
    """
    调整 Redis 中的优选分，使用哈希存储，不写入明文。
    """
    if redis is None:
        return
    member = _hash_provider_key(selection.provider_id, selection.state.key)
    zset_key = _preference_redis_key(selection.provider_id)
    try:
        await redis.zadd(zset_key, {member: _PREFERENCE_BASE}, nx=True)
        new_score = await redis.zincrby(zset_key, delta, member)
        clamped = min(max(new_score, _PREFERENCE_MIN), _PREFERENCE_MAX)
        if clamped != new_score:
            await redis.zadd(zset_key, {member: clamped})
    except Exception as exc:  # pragma: no cover - 不影响主流程
        logger.debug(
            "provider=%s preference score update skipped: %s",
            selection.provider_id,
            exc,
        )


async def acquire_provider_key(
    provider: ProviderConfig, redis: Redis | None = None
) -> SelectedProviderKey:
    """
    Choose an available key for a provider using weighted random selection.
    Keys in backoff or exceeding per-key QPS are skipped.
    """
    async with _get_lock(provider.id):
        states = _ensure_states(provider)
        now = time.time()
        candidates = [s for s in states if s.backoff_until <= now]
        if not candidates:
            raise NoAvailableProviderKey(
                f"No available keys for provider {provider.id} (all in backoff)"
            )

        preference_scores = await _load_preference_scores(redis, provider.id, candidates)
        scored_candidates = sorted(
            [
                (
                    preference_scores.get(
                        _hash_provider_key(provider.id, state.key), _PREFERENCE_BASE
                    ),
                    state,
                )
                for state in candidates
            ],
            key=lambda item: item[0],
            reverse=True,
        )

        idx = 0
        while idx < len(scored_candidates):
            current_score = scored_candidates[idx][0]
            same_score_states: list[ProviderKeyState] = []
            while (
                idx < len(scored_candidates)
                and scored_candidates[idx][0]
                >= current_score - _PREFERENCE_GROUP_TOLERANCE
            ):
                same_score_states.append(scored_candidates[idx][1])
                idx += 1

            working_set = list(same_score_states)
            while working_set:
                weights = [max(s.weight, 0.0001) for s in working_set]
                state = random.choices(working_set, weights=weights, k=1)[0]

                if not await _reserve_qps(redis, provider.id, state):
                    working_set.remove(state)
                    continue

                state.last_used_at = now
                return SelectedProviderKey(
                    provider_id=provider.id, key=state.key, label=state.label, state=state
                )

    raise NoAvailableProviderKey(
        f"No available keys for provider {provider.id} (rate limited)"
    )


def record_key_success(
    selection: SelectedProviderKey, *, redis: Redis | None = None
) -> None:
    selection.state.fail_count = 0
    selection.state.backoff_until = 0.0
    if redis is not None:
        asyncio.create_task(
            _adjust_preference_score(redis, selection, _PREFERENCE_SUCCESS_DELTA)
        )


def record_key_failure(
    selection: SelectedProviderKey,
    *,
    retryable: bool = True,
    status_code: int | None = None,
    redis: Redis | None = None,
) -> None:
    """
    Increase backoff for a key after an upstream failure.
    """
    selection.state.fail_count += 1
    base = 1.0 if retryable else 5.0
    backoff_seconds = base * (2 ** min(selection.state.fail_count, 5))
    delta = _PREFERENCE_RETRYABLE_FAILURE_DELTA if retryable else _PREFERENCE_FATAL_DELTA
    if status_code in (401, 403):
        backoff_seconds = max(backoff_seconds, 30.0)
        delta = min(delta, _PREFERENCE_AUTH_FAILURE_DELTA)
    selection.state.backoff_until = time.time() + min(backoff_seconds, 60.0)
    logger.warning(
        "provider=%s key=%s enter backoff for %.1fs (status=%s retryable=%s)",
        selection.provider_id,
        selection.label,
        backoff_seconds,
        status_code,
        retryable,
    )
    if redis is not None:
        asyncio.create_task(
            _adjust_preference_score(redis, selection, delta),
        )


def reset_key_pool(provider_id: str | None = None) -> None:
    """
    Clear cached key state (useful in tests).
    """
    if provider_id is None:
        _KEY_STATES.clear()
        _LOCKS.clear()
    else:
        _KEY_STATES.pop(provider_id, None)
        _LOCKS.pop(provider_id, None)


__all__ = [
    "NoAvailableProviderKey",
    "SelectedProviderKey",
    "acquire_provider_key",
    "record_key_failure",
    "record_key_success",
    "reset_key_pool",
]
