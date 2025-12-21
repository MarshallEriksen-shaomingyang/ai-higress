from __future__ import annotations

import datetime as dt
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.deps import get_db, get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import (
    Base,
    ProviderRoutingMetricsHistory,
    UserAppRequestMetricsHistory,
    UserRoutingMetricsHistory,
)
from app.routes import create_app
from app.services.api_key_cache import CachedAPIKey
from tests.utils import InMemoryRedis, seed_user_and_key


def _insert_sample_metrics(db: Session, *, provider_id: str, logical_model: str) -> None:
    now = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    for i in range(3):
        bucket_start = now - dt.timedelta(minutes=i)
        db.add(
            ProviderRoutingMetricsHistory(
                id=uuid4(),
                provider_id=provider_id,
                logical_model=logical_model,
                transport="http",
                is_stream=False,
                window_start=bucket_start,
                window_duration=60,
                total_requests_1m=10 + i,
                success_requests=9 + i,
                error_requests=1,
                latency_avg_ms=100.0 + i,
                latency_p95_ms=150.0 + i,
                latency_p99_ms=180.0 + i,
                error_rate=0.1,
                success_qps_1m=(9 + i) / 60.0,
                status="healthy",
            )
        )
    db.commit()


def _insert_user_metrics(
    db: Session,
    *,
    user_id: UUID,
    provider_id: str,
    logical_model: str,
) -> None:
    now = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    for i in range(3):
        bucket_start = now - dt.timedelta(minutes=i)
        db.add(
            ProviderRoutingMetricsHistory(
                id=uuid4(),
                provider_id=provider_id,
                logical_model=logical_model,
                transport="http",
                is_stream=False,
                user_id=user_id,
                api_key_id=None,
                window_start=bucket_start,
                window_duration=60,
                total_requests_1m=10 + i,
                success_requests=9 + i,
                error_requests=1,
                latency_avg_ms=100.0 + i,
                latency_p95_ms=150.0 + i,
                latency_p99_ms=180.0 + i,
                error_rate=0.1,
                success_qps_1m=(9 + i) / 60.0,
                status="healthy",
            )
        )
    db.commit()


def _insert_api_key_metrics(
    db: Session,
    *,
    api_key_id: UUID,
    provider_id: str,
    logical_model: str,
) -> None:
    now = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    for i in range(3):
        bucket_start = now - dt.timedelta(minutes=i)
        db.add(
            ProviderRoutingMetricsHistory(
                id=uuid4(),
                provider_id=provider_id,
                logical_model=logical_model,
                transport="http",
                is_stream=False,
                user_id=None,
                api_key_id=api_key_id,
                window_start=bucket_start,
                window_duration=60,
                total_requests_1m=10 + i,
                success_requests=9 + i,
                error_requests=1,
                latency_avg_ms=100.0 + i,
                latency_p95_ms=150.0 + i,
                latency_p99_ms=180.0 + i,
                error_rate=0.1,
                success_qps_1m=(9 + i) / 60.0,
                status="healthy",
            )
        )
    db.commit()


def _insert_user_overview_metrics(
    db: Session,
    *,
    user_id: UUID,
    provider_id: str,
    logical_model: str,
) -> None:
    now = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    for i in range(3):
        bucket_start = now - dt.timedelta(minutes=i)
        db.add(
            UserRoutingMetricsHistory(
                id=uuid4(),
                user_id=user_id,
                provider_id=provider_id,
                logical_model=logical_model,
                transport="http",
                is_stream=False,
                window_start=bucket_start,
                window_duration=60,
                total_requests=10 + i,
                success_requests=9 + i,
                error_requests=1,
                latency_avg_ms=100.0 + i,
                latency_p95_ms=150.0 + i,
                latency_p99_ms=180.0 + i,
                error_rate=0.1,
            )
        )
    db.commit()


def _insert_user_app_overview_metrics(db: Session, *, user_id: UUID) -> None:
    now = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    db.add(
        UserAppRequestMetricsHistory(
            id=uuid4(),
            user_id=user_id,
            api_key_id=None,
            app_name="Cherry Studio",
            window_start=now,
            window_duration=60,
            total_requests=3,
        )
    )
    db.add(
        UserAppRequestMetricsHistory(
            id=uuid4(),
            user_id=user_id,
            api_key_id=None,
            app_name="Roo Code",
            window_start=now,
            window_duration=60,
            total_requests=2,
        )
    )
    db.add(
        UserAppRequestMetricsHistory(
            id=uuid4(),
            user_id=user_id,
            api_key_id=None,
            app_name="Cherry Studio",
            window_start=now - dt.timedelta(minutes=1),
            window_duration=60,
            total_requests=4,
        )
    )
    db.commit()


@pytest.fixture()
def client_with_db():
    """Create test client with in-memory database."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db_session():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    fake_redis = InMemoryRedis()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_db] = override_get_db_session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    async def override_require_jwt_token() -> AuthenticatedUser:
        # 指标接口仅验证“已登录用户”，这里返回固定的测试用户即可
        return AuthenticatedUser(
            id="00000000-0000-0000-0000-000000000000",
            username="test",
            email="test@example.com",
            is_superuser=True,
            is_active=True,
            display_name=None,
            avatar=None,
        )

    app.dependency_overrides[require_jwt_token] = override_require_jwt_token

    with TestingSessionLocal() as session:
        seed_user_and_key(session, token_plain="timeline")

    with TestClient(app, base_url="http://test") as client:
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_metrics_timeseries_api(mock_get_cached_api_key, client_with_db):
    client, session_factory = client_with_db

    # Mock Redis cache to avoid connection timeout
    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    provider_id = "openai"
    logical_model = "gpt-4"

    with session_factory() as session:
        _insert_sample_metrics(session, provider_id=provider_id, logical_model=logical_model)

    resp = client.get(
        "/metrics/providers/timeseries",
        params={
            "provider_id": provider_id,
            "logical_model": logical_model,
            "time_range": "all",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider_id
    assert data["logical_model"] == logical_model
    assert data["time_range"] == "all"
    assert data["bucket"] == "minute"
    assert len(data["points"]) >= 3


@pytest.mark.asyncio
async def test_metrics_user_overview_apps_api(client_with_db):
    client, session_factory = client_with_db

    user_id = UUID("00000000-0000-0000-0000-000000000000")
    with session_factory() as session:
        _insert_user_app_overview_metrics(session, user_id=user_id)

    resp = client.get(
        "/metrics/user-overview/apps",
        params={"time_range": "all", "limit": 10},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "user"
    assert data["user_id"] == str(user_id)
    assert data["time_range"] == "all"
    assert len(data["items"]) == 2
    assert data["items"][0]["app_name"] == "Cherry Studio"
    assert data["items"][0]["total_requests"] == 7


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_metrics_summary_api(mock_get_cached_api_key, client_with_db):
    client, session_factory = client_with_db

    # Mock Redis cache to avoid connection timeout
    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    provider_id = "openai-summary"
    logical_model = "gpt-4"

    with session_factory() as session:
        _insert_sample_metrics(session, provider_id=provider_id, logical_model=logical_model)

    resp = client.get(
        "/metrics/providers/summary",
        params={
            "provider_id": provider_id,
            "logical_model": logical_model,
            "time_range": "all",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider_id
    assert data["logical_model"] == logical_model
    assert data["time_range"] == "all"
    # 样本中 total_requests_1m = 10,11,12 -> 总和 33
    assert data["total_requests"] == 33


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_user_metrics_summary_api(mock_get_cached_api_key, client_with_db):
    client, session_factory = client_with_db

    # Mock Redis cache to avoid connection timeout
    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    provider_id = "openai-user"
    logical_model = "gpt-4"
    user_id = uuid4()  # Use UUID object instead of string

    with session_factory() as session:
        _insert_user_metrics(
            session,
            user_id=user_id,
            provider_id=provider_id,
            logical_model=logical_model,
        )

    resp = client.get(
        "/metrics/users/summary",
        params={
            "user_id": str(user_id),  # Convert to string for API call
            "time_range": "all",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user_id)
    assert data["time_range"] == "all"
    # 样本中 total_requests_1m = 10,11,12 -> 总和 33
    assert data["total_requests"] == 33


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_api_key_metrics_summary_api(mock_get_cached_api_key, client_with_db):
    client, session_factory = client_with_db

    # Mock Redis cache to avoid connection timeout
    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    provider_id = "openai-apikey"
    logical_model = "gpt-4"
    api_key_id = uuid4()  # Use UUID object instead of string

    with session_factory() as session:
        _insert_api_key_metrics(
            session,
            api_key_id=api_key_id,
            provider_id=provider_id,
            logical_model=logical_model,
        )

    resp = client.get(
        "/metrics/api-keys/summary",
        params={
            "api_key_id": str(api_key_id),  # Convert to string for API call
            "time_range": "all",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key_id"] == str(api_key_id)
    assert data["time_range"] == "all"
    # 样本中 total_requests_1m = 10,11,12 -> 总和 33
    assert data["total_requests"] == 33


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_metrics_overview_summary_api(mock_get_cached_api_key, client_with_db):
    """
    仪表盘概览接口应能聚合多个 Provider 的全局指标，并返回总请求数与活跃 Provider 数。
    """
    client, session_factory = client_with_db

    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    with session_factory() as session:
        # 插入两个 Provider 的样本数据：每个 Provider 3 个时间桶，每桶 10,11,12 请求
        _insert_sample_metrics(session, provider_id="openai-overview", logical_model="gpt-4")
        _insert_sample_metrics(session, provider_id="anthropic-overview", logical_model="claude-3")

    resp = client.get(
        "/metrics/overview/summary",
        params={
            "time_range": "all",
            "transport": "all",
            "is_stream": "all",
        },
    )

    assert resp.status_code == 200
    data = resp.json()

    # 两个 Provider，总请求数应为 2 * (10+11+12) = 66
    assert data["total_requests"] == 66
    # 活跃 Provider 数为 2
    assert data["active_providers"] == 2


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_metrics_overview_active_providers_api(mock_get_cached_api_key, client_with_db):
    """
    活跃 Provider 概览接口应返回按请求量排序的 Provider 列表。
    """
    client, session_factory = client_with_db

    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    with session_factory() as session:
        _insert_sample_metrics(session, provider_id="openai-active", logical_model="gpt-4")
        _insert_sample_metrics(session, provider_id="anthropic-active", logical_model="claude-3")

    resp = client.get(
        "/metrics/overview/providers",
        params={
            "time_range": "all",
            "transport": "all",
            "is_stream": "all",
            "limit": 4,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["time_range"] == "all"
    items = data["items"]
    assert len(items) == 2
    provider_ids = {item["provider_id"] for item in items}
    assert provider_ids == {"openai-active", "anthropic-active"}
    # 每个 Provider 总请求数应为 33（10+11+12），成功数应为 30（9+10+11）
    for item in items:
        assert item["total_requests"] == 33
        assert item["success_requests"] == 30
        assert item["error_requests"] == 3
        assert abs(item["success_rate"] - (30 / 33)) < 1e-6


@patch("app.auth.get_cached_api_key")
@pytest.mark.asyncio
async def test_metrics_overview_timeseries_api(mock_get_cached_api_key, client_with_db):
    """
    近期活动时间序列接口应返回按时间排序的全局指标。
    """
    client, session_factory = client_with_db

    test_user_id = uuid4()
    mock_get_cached_api_key.return_value = CachedAPIKey(
        id=str(uuid4()),
        user_id=str(test_user_id),
        user_username="test_user",
        user_is_active=True,
        user_is_superuser=False,
        name="test_key",
        expires_at=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    with session_factory() as session:
        _insert_sample_metrics(session, provider_id="openai-activity", logical_model="gpt-4")
        _insert_sample_metrics(session, provider_id="anthropic-activity", logical_model="claude-3")

    resp = client.get(
        "/metrics/overview/timeseries",
        params={
            "time_range": "all",
            "bucket": "minute",
            "transport": "all",
            "is_stream": "all",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["bucket"] == "minute"
    assert data["time_range"] == "all"
    points = data["points"]
    # 至少有 3 个时间桶
    assert len(points) >= 3
    # 全局总请求应为两个 Provider 之和：2 * 33 = 66
    total_requests = sum(p["total_requests"] for p in points)
    assert total_requests == 66


@pytest.mark.asyncio
async def test_user_overview_summary_api(client_with_db):
    client, session_factory = client_with_db
    target_user_id = UUID("00000000-0000-0000-0000-000000000000")
    other_user_id = uuid4()

    with session_factory() as session:
        _insert_user_overview_metrics(
            session,
            user_id=target_user_id,
            provider_id="user-provider-a",
            logical_model="gpt-4",
        )
        _insert_user_overview_metrics(
            session,
            user_id=other_user_id,
            provider_id="user-provider-b",
            logical_model="claude-3",
        )

    resp = client.get(
        "/metrics/user-overview/summary",
        params={"time_range": "all"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(target_user_id)
    assert data["total_requests"] == 33
    assert data["active_providers"] == 1


@pytest.mark.asyncio
async def test_user_overview_providers_api(client_with_db):
    client, session_factory = client_with_db
    target_user_id = UUID("00000000-0000-0000-0000-000000000000")

    with session_factory() as session:
        _insert_user_overview_metrics(
            session,
            user_id=target_user_id,
            provider_id="user-provider-a",
            logical_model="gpt-4",
        )
        _insert_user_overview_metrics(
            session,
            user_id=target_user_id,
            provider_id="user-provider-b",
            logical_model="claude-3",
        )

    resp = client.get(
        "/metrics/user-overview/providers",
        params={"time_range": "all", "limit": 5},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(target_user_id)
    assert len(data["items"]) == 2
    provider_ids = {item["provider_id"] for item in data["items"]}
    assert provider_ids == {"user-provider-a", "user-provider-b"}


@pytest.mark.asyncio
async def test_user_overview_timeseries_empty(client_with_db):
    client, _ = client_with_db

    resp = client.get(
        "/metrics/user-overview/timeseries",
        params={"time_range": "all", "bucket": "minute"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == []
