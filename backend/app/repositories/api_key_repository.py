from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import APIKey
from app.repositories.api_key_provider_restriction_repository import (
    UnknownProviderError,
    replace_allowed_providers,
)


def api_key_name_exists(
    db: Session,
    *,
    user_id: UUID,
    name: str,
    exclude_key_id: UUID | None = None,
) -> bool:
    stmt: Select[tuple[APIKey]] = select(APIKey).where(
        APIKey.user_id == user_id, APIKey.name == name
    )
    if exclude_key_id is not None:
        stmt = stmt.where(APIKey.id != exclude_key_id)
    return db.execute(stmt).scalars().first() is not None


def list_api_keys_for_user(db: Session, *, user_id: UUID) -> list[APIKey]:
    stmt: Select[tuple[APIKey]] = (
        select(APIKey)
        .where(APIKey.user_id == user_id)
        .options(selectinload(APIKey.allowed_provider_links))
        .order_by(APIKey.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_api_key_by_id(
    db: Session,
    *,
    key_id: UUID,
    user_id: UUID | None = None,
) -> APIKey | None:
    stmt: Select[tuple[APIKey]] = select(APIKey).options(
        selectinload(APIKey.allowed_provider_links)
    )
    stmt = stmt.where(APIKey.id == key_id)
    if user_id is not None:
        stmt = stmt.where(APIKey.user_id == user_id)
    return db.execute(stmt).scalars().first()


def find_api_key_by_hash(db: Session, *, key_hash: str) -> APIKey | None:
    stmt: Select[tuple[APIKey]] = (
        select(APIKey)
        .where(APIKey.key_hash == key_hash)
        .options(
            selectinload(APIKey.allowed_provider_links),
            selectinload(APIKey.user),
        )
    )
    return db.execute(stmt).scalars().first()


def create_api_key(
    db: Session,
    *,
    user_id: UUID,
    name: str,
    key_hash: str,
    key_prefix: str,
    expiry_type: str,
    expires_at: datetime | None,
    is_active: bool,
    disabled_reason: str | None,
    allowed_provider_ids: list[str] | None,
) -> APIKey:
    api_key = APIKey(
        user_id=user_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expiry_type=expiry_type,
        expires_at=expires_at,
        is_active=is_active,
        disabled_reason=disabled_reason,
    )

    db.add(api_key)
    db.flush()  # ensure api_key.id for relationship inserts
    try:
        if allowed_provider_ids is not None:
            replace_allowed_providers(db, api_key=api_key, provider_ids=allowed_provider_ids)
        db.commit()
    except UnknownProviderError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(api_key)
    return api_key


def persist_api_key(
    db: Session,
    *,
    api_key: APIKey,
    allowed_provider_ids: list[str] | None = None,
) -> APIKey:
    db.add(api_key)
    try:
        if allowed_provider_ids is not None:
            replace_allowed_providers(db, api_key=api_key, provider_ids=allowed_provider_ids)
        db.commit()
    except UnknownProviderError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(api_key)
    return api_key


def delete_api_key(db: Session, *, api_key: APIKey) -> None:
    db.delete(api_key)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


__all__ = [
    "api_key_name_exists",
    "create_api_key",
    "delete_api_key",
    "find_api_key_by_hash",
    "get_api_key_by_id",
    "list_api_keys_for_user",
    "persist_api_key",
]

