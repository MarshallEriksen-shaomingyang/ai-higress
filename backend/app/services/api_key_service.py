from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import APIKey, User
from app.schemas.api_key import APIKeyCreateRequest, APIKeyExpiry, APIKeyUpdateRequest
from app.settings import settings
from .api_key_provider_restriction import (
    APIKeyProviderRestrictionService,
    UnknownProviderError,
)

API_KEY_PREFIX_LENGTH = 12


class APIKeyServiceError(Exception):
    """Base error for API key operations."""


class APIKeyNameAlreadyExistsError(APIKeyServiceError):
    """Raised when a user reuses an existing key name."""


def build_api_key_prefix(token: str) -> str:
    return token[:API_KEY_PREFIX_LENGTH]


def derive_api_key_hash(token: str) -> str:
    secret = settings.secret_key.encode("utf-8")
    message = token.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _expires_at_for(expiry: APIKeyExpiry) -> datetime | None:
    if expiry is APIKeyExpiry.NEVER:
        return None
    delta_map = {
        APIKeyExpiry.WEEK: timedelta(days=7),
        APIKeyExpiry.MONTH: timedelta(days=30),
        APIKeyExpiry.YEAR: timedelta(days=365),
    }
    delta = delta_map.get(expiry)
    if delta is None:
        return None
    return datetime.now(UTC) + delta


def _name_exists(
    session: Session,
    user_id: UUID,
    name: str,
    *,
    exclude_key_id: UUID | None = None,
) -> bool:
    stmt: Select[tuple[APIKey]] = select(APIKey).where(
        APIKey.user_id == user_id, APIKey.name == name
    )
    if exclude_key_id is not None:
        stmt = stmt.where(APIKey.id != exclude_key_id)
    return session.execute(stmt).scalars().first() is not None


def list_api_keys_for_user(session: Session, user_id: UUID) -> list[APIKey]:
    stmt: Select[tuple[APIKey]] = (
        select(APIKey)
        .where(APIKey.user_id == user_id)
        .options(selectinload(APIKey.allowed_provider_links))
        .order_by(APIKey.created_at.asc())
    )
    return list(session.execute(stmt).scalars().all())


def get_api_key_by_id(
    session: Session, key_id: UUID | str, *, user_id: UUID | None = None
) -> APIKey | None:
    stmt: Select[tuple[APIKey]] = select(APIKey).options(
        selectinload(APIKey.allowed_provider_links)
    )
    try:
        key_uuid = UUID(str(key_id))
    except ValueError:
        return None
    stmt = stmt.where(APIKey.id == key_uuid)
    if user_id is not None:
        stmt = stmt.where(APIKey.user_id == user_id)
    return session.execute(stmt).scalars().first()


def find_api_key_by_hash(session: Session, key_hash: str) -> APIKey | None:
    stmt: Select[tuple[APIKey]] = (
        select(APIKey)
        .where(APIKey.key_hash == key_hash)
        .options(
            selectinload(APIKey.allowed_provider_links),
            selectinload(APIKey.user),
        )
    )
    return session.execute(stmt).scalars().first()


def create_api_key(
    session: Session,
    *,
    user: User,
    payload: APIKeyCreateRequest,
) -> tuple[APIKey, str]:
    if _name_exists(session, user.id, payload.name):
        raise APIKeyNameAlreadyExistsError("duplicate api key name")

    token = secrets.token_urlsafe(48)
    print(f"API token length: {len(token.encode('utf-8'))} bytes")
    if len(token.encode('utf-8')) > 72:
        token = token[:72]
        print(f"Truncated API token to: {len(token.encode('utf-8'))} bytes")
    api_key = APIKey(
        user_id=user.id,
        name=payload.name,
        key_hash=derive_api_key_hash(token),
        key_prefix=build_api_key_prefix(token),
        expiry_type=payload.expiry.value,
        expires_at=_expires_at_for(payload.expiry),
        is_active=True,
        disabled_reason=None,
    )

    session.add(api_key)
    session.flush()  # ensure api_key.id for relationship inserts
    restrictions = APIKeyProviderRestrictionService(session)
    try:
        if payload.allowed_provider_ids is not None:
            restrictions.set_allowed_providers(api_key, payload.allowed_provider_ids)
        session.commit()
    except UnknownProviderError:
        session.rollback()
        raise
    except IntegrityError as exc:  # pragma: no cover - 极低概率的并发写冲突
        session.rollback()
        raise APIKeyServiceError("无法创建密钥") from exc
    session.refresh(api_key)
    return api_key, token


def update_api_key(
    session: Session,
    *,
    api_key: APIKey,
    payload: APIKeyUpdateRequest,
) -> APIKey:
    if payload.name is not None and payload.name != api_key.name:
        if _name_exists(
            session,
            api_key.user_id,
            payload.name,
            exclude_key_id=api_key.id,
        ):
            raise APIKeyNameAlreadyExistsError("duplicate api key name")
        api_key.name = payload.name

    if payload.expiry is not None:
        api_key.expiry_type = payload.expiry.value
        api_key.expires_at = _expires_at_for(payload.expiry)
        if api_key.expires_at is None or api_key.expires_at > datetime.now(UTC):
            if api_key.disabled_reason == "expired":
                api_key.is_active = True
                api_key.disabled_reason = None
        elif api_key.expires_at <= datetime.now(UTC):
            api_key.is_active = False
            api_key.disabled_reason = "expired"

    restrictions = APIKeyProviderRestrictionService(session)
    try:
        if payload.allowed_provider_ids is not None:
            restrictions.set_allowed_providers(api_key, payload.allowed_provider_ids)
        session.add(api_key)
        session.commit()
    except UnknownProviderError:
        session.rollback()
        raise
    except IntegrityError as exc:  # pragma: no cover - 极低概率的并发写冲突
        session.rollback()
        raise APIKeyServiceError("无法更新密钥") from exc
    session.refresh(api_key)
    return api_key


def delete_api_key(session: Session, api_key: APIKey) -> None:
    session.delete(api_key)
    session.commit()


__all__ = [
    "APIKeyNameAlreadyExistsError",
    "APIKeyServiceError",
    "API_KEY_PREFIX_LENGTH",
    "build_api_key_prefix",
    "create_api_key",
    "delete_api_key",
    "derive_api_key_hash",
    "find_api_key_by_hash",
    "get_api_key_by_id",
    "list_api_keys_for_user",
    "update_api_key",
]
