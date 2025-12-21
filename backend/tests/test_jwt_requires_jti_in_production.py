from __future__ import annotations

import asyncio

from app.models import User
from app.services.jwt_auth_service import create_access_token, create_access_token_with_jti
from app.services.token_redis_service import TokenRedisService
from app.settings import settings


def test_jwt_without_jti_rejected_in_production(client, db_session, monkeypatch) -> None:
    user = db_session.query(User).first()
    assert user is not None

    monkeypatch.setattr(settings, "environment", "production", raising=False)

    legacy_token = create_access_token({"sub": str(user.id)})
    resp = client.post(
        "/system/secret-key/generate",
        json={"length": 32},
        headers={"Authorization": f"Bearer {legacy_token}"},
    )
    assert resp.status_code == 401


def test_jwt_with_jti_and_redis_record_accepted_in_production(client, db_session, monkeypatch) -> None:
    user = db_session.query(User).first()
    assert user is not None

    monkeypatch.setattr(settings, "environment", "production", raising=False)

    access_token, access_jti, access_token_id = create_access_token_with_jti({"sub": str(user.id)})
    redis = client.app.state._test_redis
    token_service = TokenRedisService(redis)

    asyncio.run(
        token_service.store_access_token(
            token_id=access_token_id,
            user_id=str(user.id),
            jti=access_jti,
            expires_in=60,
        )
    )

    resp = client.post(
        "/system/secret-key/generate",
        json={"length": 32},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert "secret_key" in resp.json()

