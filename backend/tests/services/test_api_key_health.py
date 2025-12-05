from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import APIKey, Base, ProviderRoutingMetricsHistory, User
from app.services.api_key_health import disable_error_prone_api_keys, disable_expired_api_keys
from app.services.api_key_service import APIKeyExpiry, build_api_key_prefix, derive_api_key_hash


def _setup_session() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_user_and_key(session: Session, *, expires_at: datetime | None = None) -> APIKey:
    user = User(
        username="bob",
        email="bob@example.com",
        hashed_password="secret",
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.flush()

    token_plain = "health-check"
    api_key = APIKey(
        user_id=user.id,
        name="bob-key",
        key_hash=derive_api_key_hash(token_plain),
        key_prefix=build_api_key_prefix(token_plain),
        expiry_type=APIKeyExpiry.MONTH.value,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key


def test_disable_expired_api_keys_sets_flag_and_reason():
    SessionLocal = _setup_session()
    with SessionLocal() as session:
        expired_at = datetime.now(UTC) - timedelta(days=1)
        api_key = _seed_user_and_key(session, expires_at=expired_at)
        disabled_count = disable_expired_api_keys(session)
        assert disabled_count == 1
        refreshed = session.get(APIKey, api_key.id)
        assert refreshed.is_active is False
        assert refreshed.disabled_reason == "expired"


def test_disable_error_prone_api_keys_uses_metrics_window():
    SessionLocal = _setup_session()
    with SessionLocal() as session:
        api_key = _seed_user_and_key(session, expires_at=None)
        metrics = ProviderRoutingMetricsHistory(
            provider_id="mock",
            logical_model="gpt-3",
            transport="http",
            is_stream=False,
            user_id=None,
            api_key_id=api_key.id,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_duration=60,
            total_requests_1m=50,
            success_requests=10,
            error_requests=40,
            latency_avg_ms=120.0,
            latency_p95_ms=180.0,
            latency_p99_ms=220.0,
            error_rate=0.8,
            success_qps_1m=0.2,
            status="degraded",
        )
        session.add(metrics)
        session.commit()

        disabled_count = disable_error_prone_api_keys(
            session,
            window_minutes=15,
            error_rate_threshold=0.6,
            min_total_requests=10,
        )
        assert disabled_count == 1
        refreshed = session.get(APIKey, api_key.id)
        assert refreshed.is_active is False
        assert refreshed.disabled_reason == "high_error_rate"
