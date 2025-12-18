from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CreditAccount, CreditTransaction, Provider, ProviderRoutingMetricsHistory, User
from tests.utils import jwt_auth_headers


def _seed_provider(db: Session, *, provider_id: str = "openai", transport: str = "http") -> Provider:
    provider = Provider(
        provider_id=provider_id,
        name=provider_id,
        base_url="https://example.invalid",
        transport=transport,
        provider_type="native",
        weight=1.0,
        status="healthy",
        audit_status="approved",
        operation_status="active",
        probe_enabled=False,
        visibility="public",
        billing_factor=1.0,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _get_admin_user(db: Session) -> User:
    user = db.query(User).first()
    assert user is not None
    return user


def test_user_dashboard_v2_kpis(client: TestClient, db_session: Session) -> None:
    user = _get_admin_user(db_session)
    _seed_provider(db_session, provider_id="openai", transport="http")

    now = dt.datetime.now(dt.timezone.utc)
    window_start = (now - dt.timedelta(minutes=5)).replace(second=0, microsecond=0)

    db_session.add(
        ProviderRoutingMetricsHistory(
            provider_id="openai",
            logical_model="gpt-4-turbo",
            transport="http",
            is_stream=False,
            user_id=user.id,
            api_key_id=None,
            window_start=window_start,
            window_duration=60,
            total_requests_1m=10,
            success_requests=9,
            error_requests=1,
            latency_avg_ms=100.0,
            latency_p50_ms=90.0,
            latency_p95_ms=200.0,
            latency_p99_ms=250.0,
            error_rate=0.1,
            success_qps_1m=0.15,
            status="healthy",
            input_tokens_sum=1000,
            output_tokens_sum=500,
            total_tokens_sum=1500,
            token_estimated_requests=2,
            error_4xx_requests=1,
            error_5xx_requests=0,
            error_429_requests=0,
            error_timeout_requests=0,
        )
    )

    account = CreditAccount(user_id=user.id, balance=1000, status="active")
    db_session.add(account)
    db_session.flush()
    db_session.add(
        CreditTransaction(
            account_id=account.id,
            user_id=user.id,
            api_key_id=None,
            amount=-42,
            reason="usage",
            description=None,
            model_name="gpt-4-turbo",
            provider_id="openai",
            provider_model_id="gpt-4-turbo",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            idempotency_key="test-kpis",
        )
    )
    db_session.commit()

    resp = client.get(
        "/metrics/user-dashboard/kpis?time_range=today",
        headers=jwt_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["time_range"] == "today"
    assert payload["total_requests"] >= 10
    assert payload["tokens"]["total"] >= 1500
    assert payload["tokens"]["estimated_requests"] >= 2
    assert payload["credits_spent"] >= 42


def test_system_dashboard_v2_requires_superuser(client: TestClient, db_session: Session) -> None:
    admin = _get_admin_user(db_session)
    assert admin.is_superuser is True

    normal = User(
        username="normal",
        email="normal@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(normal)
    db_session.commit()
    db_session.refresh(normal)

    denied = client.get(
        "/metrics/system-dashboard/kpis",
        headers=jwt_auth_headers(str(normal.id)),
    )
    assert denied.status_code == 403

    allowed = client.get(
        "/metrics/system-dashboard/kpis",
        headers=jwt_auth_headers(str(admin.id)),
    )
    assert allowed.status_code == 200


def test_system_dashboard_v2_providers(client: TestClient, db_session: Session) -> None:
    admin = _get_admin_user(db_session)
    _seed_provider(db_session, provider_id="openai", transport="http")

    resp = client.get(
        "/metrics/system-dashboard/providers",
        headers=jwt_auth_headers(str(admin.id)),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert any(item["provider_id"] == "openai" for item in payload["items"])


def test_user_dashboard_v2_providers_metrics(client: TestClient, db_session: Session) -> None:
    user = _get_admin_user(db_session)
    _seed_provider(db_session, provider_id="openai", transport="http")
    _seed_provider(db_session, provider_id="anthropic", transport="http")

    now = dt.datetime.now(dt.timezone.utc)
    window_start = (now - dt.timedelta(minutes=10)).replace(second=0, microsecond=0)

    db_session.add_all(
        [
            ProviderRoutingMetricsHistory(
                provider_id="openai",
                logical_model="gpt-4o",
                transport="http",
                is_stream=False,
                user_id=user.id,
                api_key_id=None,
                window_start=window_start,
                window_duration=60,
                total_requests_1m=60,
                success_requests=57,
                error_requests=3,
                latency_avg_ms=120.0,
                latency_p50_ms=100.0,
                latency_p95_ms=250.0,
                latency_p99_ms=300.0,
                error_rate=0.05,
                success_qps_1m=0.95,
                status="healthy",
                input_tokens_sum=0,
                output_tokens_sum=0,
                total_tokens_sum=0,
                token_estimated_requests=0,
                error_4xx_requests=0,
                error_5xx_requests=3,
                error_429_requests=0,
                error_timeout_requests=0,
            ),
            ProviderRoutingMetricsHistory(
                provider_id="anthropic",
                logical_model="claude-3-5-sonnet",
                transport="http",
                is_stream=False,
                user_id=user.id,
                api_key_id=None,
                window_start=window_start,
                window_duration=60,
                total_requests_1m=10,
                success_requests=10,
                error_requests=0,
                latency_avg_ms=80.0,
                latency_p50_ms=70.0,
                latency_p95_ms=150.0,
                latency_p99_ms=200.0,
                error_rate=0.0,
                success_qps_1m=0.16,
                status="healthy",
                input_tokens_sum=0,
                output_tokens_sum=0,
                total_tokens_sum=0,
                token_estimated_requests=0,
                error_4xx_requests=0,
                error_5xx_requests=0,
                error_429_requests=0,
                error_timeout_requests=0,
            ),
        ]
    )
    db_session.commit()

    resp = client.get(
        "/metrics/user-dashboard/providers?time_range=today&provider_ids=openai",
        headers=jwt_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["time_range"] == "today"
    assert payload["bucket"] == "hour"
    assert payload["items"][0]["provider_id"] == "openai"
    assert payload["items"][0]["total_requests"] >= 60
    assert payload["items"][0]["error_rate"] > 0
    assert payload["items"][0]["latency_p95_ms"] > 0
    assert payload["items"][0]["qps"] >= 0
    assert payload["items"][0]["points"]
