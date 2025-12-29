from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from app.settings import settings

_ISSUER = "ai-higress"
_TOKEN_TYPE = "credit_grant"


@dataclass(frozen=True)
class CreditGrantTokenData:
    amount: int
    reason: str
    description: str | None
    idempotency_key: str
    target_user_id: UUID | None
    issued_at: datetime.datetime
    expires_at: datetime.datetime


def _require_secret_key() -> str:
    secret = (settings.secret_key or "").strip()
    if not secret:
        raise RuntimeError("missing SECRET_KEY")
    return secret


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.UTC)
    return value.astimezone(datetime.UTC)


def _parse_ts(value: Any, *, field: str) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return _as_utc(value)
    try:
        return datetime.datetime.fromtimestamp(int(value), tz=datetime.UTC)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"invalid {field}") from exc


def create_credit_grant_token(
    *,
    target_user_id: UUID | None,
    amount: int,
    reason: str,
    description: str | None = None,
    idempotency_key: str | None = None,
    issued_at: datetime.datetime | None = None,
    expires_in_seconds: int = 86400,
) -> tuple[str, datetime.datetime, datetime.datetime]:
    """
    Create a signed token for granting credits.

    Claims (HS256):
    - type=credit_grant
    - sub=<user_id> (optional, when token is user-bound)
    - amount/reason/description/idempotency_key
    - iat/exp/iss
    """
    if int(amount) <= 0:
        raise ValueError("amount 必须为正整数")
    if not (reason or "").strip():
        raise ValueError("missing reason")
    if len(reason) > 32:
        raise ValueError("reason 过长（最长 32 字符）")

    key = (idempotency_key or "").strip()
    if not key:
        key = f"credit_grant:{uuid.uuid4().hex}"
    if len(key) > 80:
        raise ValueError("idempotency_key 过长（最长 80 字符）")

    now = _as_utc(issued_at or datetime.datetime.now(datetime.UTC))
    if int(expires_in_seconds) < 60:
        raise ValueError("expires_in_seconds 过短（至少 60 秒）")
    expire = now + datetime.timedelta(seconds=int(expires_in_seconds))

    payload: dict[str, Any] = {
        "type": _TOKEN_TYPE,
        "amount": int(amount),
        "reason": reason.strip(),
        "description": (description or None),
        "idempotency_key": key,
        "iat": now,
        "exp": expire,
        "iss": _ISSUER,
    }
    if target_user_id is not None:
        payload["sub"] = str(target_user_id)

    token = jwt.encode(payload, _require_secret_key(), algorithm="HS256")
    return token, now, expire


def decode_credit_grant_token(token: str) -> CreditGrantTokenData:
    try:
        payload = jwt.decode(token, _require_secret_key(), algorithms=["HS256"])
    except ExpiredSignatureError as exc:
        raise ValueError("token 已过期") from exc
    except JWTError as exc:
        raise ValueError("token 无效") from exc

    if payload.get("type") != _TOKEN_TYPE:
        raise ValueError("token 类型不匹配")
    if payload.get("iss") != _ISSUER:
        raise ValueError("token issuer 不匹配")

    amount = int(payload.get("amount") or 0)
    if amount <= 0:
        raise ValueError("token amount 非法")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ValueError("token reason 缺失")
    if len(reason) > 32:
        raise ValueError("token reason 非法")

    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not idempotency_key:
        raise ValueError("token idempotency_key 缺失")
    if len(idempotency_key) > 80:
        raise ValueError("token idempotency_key 非法")

    sub = (payload.get("sub") or "").strip()
    target_user_id = UUID(sub) if sub else None

    issued_at = _parse_ts(payload.get("iat"), field="iat")
    expires_at = _parse_ts(payload.get("exp"), field="exp")

    description_val = payload.get("description")
    description = str(description_val) if description_val is not None else None
    if description is not None and len(description) > 255:
        raise ValueError("token description 非法")

    return CreditGrantTokenData(
        amount=amount,
        reason=reason,
        description=description,
        idempotency_key=idempotency_key,
        target_user_id=target_user_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )


__all__ = [
    "CreditGrantTokenData",
    "create_credit_grant_token",
    "decode_credit_grant_token",
]

