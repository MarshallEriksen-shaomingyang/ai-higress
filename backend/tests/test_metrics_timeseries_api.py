from __future__ import annotations

import datetime as dt
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import ProviderRoutingMetricsHistory


def _insert_sample_metrics(db: Session, *, provider_id: str, logical_model: str) -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
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
    user_id: str,
    provider_id: str,
    logical_model: str,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
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
    api_key_id: str,
    provider_id: str,
    logical_model: str,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
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


def test_metrics_timeseries_api(client, db_session: Session, api_key_auth_header):
    provider_id = "openai"
    logical_model = "gpt-4"
    _insert_sample_metrics(db_session, provider_id=provider_id, logical_model=logical_model)

    resp = client.get(
        "/metrics/providers/timeseries",
        params={
            "provider_id": provider_id,
            "logical_model": logical_model,
            "time_range": "all",
        },
        headers=api_key_auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider_id
    assert data["logical_model"] == logical_model
    assert data["time_range"] == "all"
    assert data["bucket"] == "minute"
    assert len(data["points"]) >= 3


def test_metrics_summary_api(client, db_session: Session, api_key_auth_header):
    provider_id = "openai-summary"
    logical_model = "gpt-4"
    _insert_sample_metrics(db_session, provider_id=provider_id, logical_model=logical_model)

    resp = client.get(
        "/metrics/providers/summary",
        params={
            "provider_id": provider_id,
            "logical_model": logical_model,
            "time_range": "all",
        },
        headers=api_key_auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider_id
    assert data["logical_model"] == logical_model
    assert data["time_range"] == "all"
    # 样本中 total_requests_1m = 10,11,12 -> 总和 33
    assert data["total_requests"] == 33


def test_user_metrics_summary_api(client, db_session: Session, api_key_auth_header):
    provider_id = "openai-user"
    logical_model = "gpt-4"
    user_id = str(uuid4())
    _insert_user_metrics(
        db_session,
        user_id=user_id,
        provider_id=provider_id,
        logical_model=logical_model,
    )

    resp = client.get(
        "/metrics/users/summary",
        params={
            "user_id": user_id,
            "time_range": "all",
        },
        headers=api_key_auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == user_id
    assert data["time_range"] == "all"
    # 样本中 total_requests_1m = 10,11,12 -> 总和 33
    assert data["total_requests"] == 33


def test_api_key_metrics_summary_api(
    client, db_session: Session, api_key_auth_header
):
    provider_id = "openai-apikey"
    logical_model = "gpt-4"
    api_key_id = str(uuid4())
    _insert_api_key_metrics(
        db_session,
        api_key_id=api_key_id,
        provider_id=provider_id,
        logical_model=logical_model,
    )

    resp = client.get(
        "/metrics/api-keys/summary",
        params={
            "api_key_id": api_key_id,
            "time_range": "all",
        },
        headers=api_key_auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key_id"] == api_key_id
    assert data["time_range"] == "all"
    # 样本中 total_requests_1m = 10,11,12 -> 总和 33
    assert data["total_requests"] == 33
