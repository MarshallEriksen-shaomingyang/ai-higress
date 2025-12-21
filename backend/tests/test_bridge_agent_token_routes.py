"""
Bridge Agent token routes tests.
"""

from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models import User
from app.settings import settings
from tests.utils import jwt_auth_headers


def test_issue_agent_token_ok(client: TestClient, db_session: Session):
    user = db_session.execute(select(User)).scalars().first()
    assert user is not None

    resp = client.post(
        "/v1/bridge/agent-token",
        headers=jwt_auth_headers(str(user.id)),
        json={"agent_id": "my-agent"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == "my-agent"
    assert isinstance(data["token"], str) and data["token"]
    assert "expires_at" in data

    claims = jwt.decode(data["token"], settings.secret_key, algorithms=["HS256"])
    assert claims["type"] == "bridge_agent"
    assert claims["sub"] == str(user.id)
    assert claims["agent_id"] == "my-agent"


def test_issue_agent_token_invalid_agent_id(client: TestClient, db_session: Session):
    user = db_session.execute(select(User)).scalars().first()
    assert user is not None

    resp = client.post(
        "/v1/bridge/agent-token",
        headers=jwt_auth_headers(str(user.id)),
        json={"agent_id": "bad id"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
