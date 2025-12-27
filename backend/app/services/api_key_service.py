from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import APIKey, User
from app.repositories.api_key_repository import (
    api_key_name_exists,
    create_api_key as repo_create_api_key,
    delete_api_key as repo_delete_api_key,
    find_api_key_by_hash as repo_find_api_key_by_hash,
    get_api_key_by_id as repo_get_api_key_by_id,
    list_api_keys_for_user as repo_list_api_keys_for_user,
    persist_api_key as repo_persist_api_key,
)
from app.schemas.api_key import APIKeyCreateRequest, APIKeyExpiry, APIKeyUpdateRequest
from app.settings import settings

from .api_key_provider_restriction import (
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
    return api_key_name_exists(
        session,
        user_id=user_id,
        name=name,
        exclude_key_id=exclude_key_id,
    )


def list_api_keys_for_user(session: Session, user_id: UUID) -> list[APIKey]:
    return repo_list_api_keys_for_user(session, user_id=user_id)


def get_api_key_by_id(
    session: Session, key_id: UUID | str, *, user_id: UUID | None = None
) -> APIKey | None:
    try:
        key_uuid = UUID(str(key_id))
    except ValueError:
        return None
    return repo_get_api_key_by_id(session, key_id=key_uuid, user_id=user_id)


def find_api_key_by_hash(session: Session, key_hash: str) -> APIKey | None:
    return repo_find_api_key_by_hash(session, key_hash=key_hash)


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
    try:
        api_key = repo_create_api_key(
            session,
            user_id=user.id,
            name=payload.name,
            key_hash=derive_api_key_hash(token),
            key_prefix=build_api_key_prefix(token),
            expiry_type=payload.expiry.value,
            expires_at=_expires_at_for(payload.expiry),
            is_active=True,
            disabled_reason=None,
            allowed_provider_ids=payload.allowed_provider_ids,
        )
    except UnknownProviderError:
        raise
    except IntegrityError as exc:  # pragma: no cover - 极低概率的并发写冲突
        raise APIKeyServiceError("无法创建密钥") from exc
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

    try:
        api_key = repo_persist_api_key(
            session,
            api_key=api_key,
            allowed_provider_ids=payload.allowed_provider_ids,
        )
    except UnknownProviderError:
        raise
    except IntegrityError as exc:  # pragma: no cover - 极低概率的并发写冲突
        raise APIKeyServiceError("无法更新密钥") from exc
    return api_key


def delete_api_key(session: Session, api_key: APIKey) -> None:
    repo_delete_api_key(session, api_key=api_key)


__all__ = [
    "API_KEY_PREFIX_LENGTH",
    "APIKeyNameAlreadyExistsError",
    "APIKeyServiceError",
    "build_api_key_prefix",
    "create_api_key",
    "delete_api_key",
    "derive_api_key_hash",
    "find_api_key_by_hash",
    "get_api_key_by_id",
    "list_api_keys_for_user",
    "update_api_key",
]
