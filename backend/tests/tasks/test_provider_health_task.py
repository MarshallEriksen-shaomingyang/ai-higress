import json
import time

import pytest

from app.models import Provider, ProviderAPIKey
from app.schemas import ProviderStatus
from app.services.encryption import encrypt_secret
from app.services.provider_health_service import (
    HEALTH_STATUS_KEY_TEMPLATE,
    get_health_status_with_fallback,
)
from app.tasks import provider_health
from app.provider.health import HealthStatus
from tests.utils import InMemoryRedis


@pytest.fixture()
def provider_record(db_session):
    provider = Provider(
        provider_id="mock",
        name="Mock",
        base_url="https://api.mock.local",
        transport="http",
        models_path="/v1/models",
    )
    provider.api_keys = [
        ProviderAPIKey(
            encrypted_key=encrypt_secret("sk-test"),
            status="active",
            label="primary",
        )
    ]
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.mark.asyncio
async def test_run_checks_updates_db_and_cache(monkeypatch, db_session, provider_record):
    redis = InMemoryRedis()

    async def _fake_check(client, cfg, redis_client):
        return HealthStatus(
            provider_id=cfg.id,
            status=ProviderStatus.HEALTHY,
            timestamp=123.0,
            response_time_ms=12.5,
            error_message=None,
            last_successful_check=120.0,
        )

    monkeypatch.setattr("app.tasks.provider_health.check_provider_health", _fake_check)

    updated = await provider_health._run_checks(
        redis,
        db_session,
        cache_ttl_seconds=60,
    )

    assert updated == 1

    key = HEALTH_STATUS_KEY_TEMPLATE.format(provider_id="mock")
    cached = json.loads(await redis.get(key))
    assert cached["status"] == ProviderStatus.HEALTHY
    assert cached["response_time_ms"] == pytest.approx(12.5)

    db_session.refresh(provider_record)
    assert provider_record.status == ProviderStatus.HEALTHY
    assert provider_record.last_check is not None
    assert provider_record.metadata_json["last_successful_check"] == 120.0


@pytest.mark.asyncio
async def test_get_health_status_with_fallback_prefers_cache(
    db_session, provider_record
):
    redis = InMemoryRedis()
    now = time.time()

    provider_record.status = ProviderStatus.DOWN.value
    provider_record.last_check = None
    db_session.add(provider_record)
    db_session.commit()

    cached = HealthStatus(
        provider_id="mock",
        status=ProviderStatus.DEGRADED,
        timestamp=now,
        response_time_ms=33.3,
        error_message="rate limited",
        last_successful_check=None,
    )
    key = HEALTH_STATUS_KEY_TEMPLATE.format(provider_id="mock")
    await redis.set(key, cached.model_dump_json())

    result = await get_health_status_with_fallback(redis, db_session, "mock")
    assert result is not None
    assert result.status == ProviderStatus.DEGRADED
    assert result.response_time_ms == pytest.approx(33.3)

    # 当缓存被清理时，应回退到数据库记录：
    # 之前实现会因为 last_check 为空返回 None，导致上层误认为 Provider 不存在。
    # 现在应返回一个基于 Provider.status 的默认健康状态。
    await redis.delete(key)
    fallback = await get_health_status_with_fallback(redis, db_session, "mock")
    assert fallback is not None
    assert fallback.status == ProviderStatus.DOWN
    # 对于从未巡检过的记录，响应时间等细节可能为空，但对象本身必须存在
    assert fallback.response_time_ms is None or fallback.response_time_ms >= 0
