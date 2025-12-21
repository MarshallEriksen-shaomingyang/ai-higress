from __future__ import annotations

import datetime
import re
import uuid
from typing import Any

from jose import jwt

from app.settings import settings

_AGENT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$")


def normalize_agent_id(value: str | None) -> str:
    agent_id = (value or "").strip()
    return agent_id


def generate_agent_id() -> str:
    return "agent_" + uuid.uuid4().hex[:10]


def validate_agent_id(agent_id: str) -> None:
    if not agent_id:
        raise ValueError("missing agent_id")
    if not _AGENT_ID_RE.fullmatch(agent_id):
        raise ValueError("invalid agent_id")


def create_bridge_agent_token(*, user_id: str, agent_id: str) -> tuple[str, datetime.datetime]:
    """
    Create a signed JWT token used by Bridge Agent to authenticate to Tunnel Gateway.

    Claims (HS256):
    - type=bridge_agent
    - sub=<user_id>
    - agent_id=<agent_id>
    - iat/exp
    """
    validate_agent_id(agent_id)

    now = datetime.datetime.now(datetime.UTC)
    expire = now + datetime.timedelta(days=int(settings.bridge_agent_token_expire_days))

    secret = (settings.secret_key or "").strip()
    if not secret:
        raise RuntimeError("missing SECRET_KEY")

    payload: dict[str, Any] = {
        "type": "bridge_agent",
        "sub": str(user_id),
        "agent_id": agent_id,
        "iat": now,
        "exp": expire,
        "iss": "ai-higress",
    }
    return jwt.encode(payload, secret, algorithm="HS256"), expire
