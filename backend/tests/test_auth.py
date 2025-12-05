import base64

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import require_api_key
from app.models import Base
from tests.utils import InMemoryRedis, seed_user_and_key


@pytest.mark.asyncio
async def test_require_api_key_queries_database() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        user, _ = seed_user_and_key(session, token_plain="custom-secret")

    encoded = base64.b64encode(b"custom-secret").decode("ascii")
    authorization = f"Bearer {encoded}"

    fake_redis = InMemoryRedis()
    with SessionLocal() as session:
        authenticated = await require_api_key(
            authorization=authorization, db=session, redis=fake_redis
        )

    assert authenticated.user_id == user.id

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_require_api_key_reads_from_cache(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        seed_user_and_key(session, token_plain="cached-secret")

    encoded = base64.b64encode(b"cached-secret").decode("ascii")
    authorization = f"Bearer {encoded}"
    fake_redis = InMemoryRedis()

    with SessionLocal() as session:
        await require_api_key(authorization=authorization, db=session, redis=fake_redis)

    def _fail(*_args, **_kwargs):
        raise AssertionError("Database lookup should not be triggered when cache is warm")

    monkeypatch.setattr(
        "app.services.api_key_service.find_api_key_by_hash", _fail, raising=False
    )

    with SessionLocal() as session:
        authenticated = await require_api_key(
            authorization=authorization, db=session, redis=fake_redis
        )

    assert authenticated.user_username == "admin"

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_disabled_api_key_is_rejected() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        user, key = seed_user_and_key(session, token_plain="inactive")
        key.is_active = False
        key.disabled_reason = "expired"
        session.add(key)
        session.commit()

    encoded = base64.b64encode(b"inactive").decode("ascii")
    authorization = f"Bearer {encoded}"
    fake_redis = InMemoryRedis()

    with SessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(authorization=authorization, db=session, redis=fake_redis)

    assert exc_info.value.status_code == 403
    assert "expired" in exc_info.value.detail

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
