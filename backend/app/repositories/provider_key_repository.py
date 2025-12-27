from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import ProviderAPIKey


def list_provider_keys(db: Session, *, provider_uuid: object) -> list[ProviderAPIKey]:
    stmt: Select[tuple[ProviderAPIKey]] = (
        select(ProviderAPIKey)
        .options(selectinload(ProviderAPIKey.provider))
        .where(ProviderAPIKey.provider_uuid == provider_uuid)
        .order_by(ProviderAPIKey.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_provider_keys_plain(db: Session, *, provider_uuid: object) -> list[ProviderAPIKey]:
    stmt: Select[tuple[ProviderAPIKey]] = select(ProviderAPIKey).where(
        ProviderAPIKey.provider_uuid == provider_uuid
    )
    return list(db.execute(stmt).scalars().all())


def get_provider_key_by_id(db: Session, *, key_id: object) -> ProviderAPIKey | None:
    try:
        return db.get(ProviderAPIKey, key_id)
    except Exception:
        return None


def find_key_by_label(
    db: Session,
    *,
    provider_uuid: object,
    label: str,
    exclude_key_id: object | None = None,
) -> ProviderAPIKey | None:
    stmt: Select[tuple[ProviderAPIKey]] = select(ProviderAPIKey).where(
        ProviderAPIKey.provider_uuid == provider_uuid,
        ProviderAPIKey.label == label,
    )
    if exclude_key_id is not None:
        stmt = stmt.where(ProviderAPIKey.id != exclude_key_id)
    return db.execute(stmt).scalars().first()


def create_provider_key(db: Session, *, api_key: ProviderAPIKey) -> ProviderAPIKey:
    db.add(api_key)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(api_key)
    return api_key


def persist_provider_key(db: Session, *, api_key: ProviderAPIKey) -> ProviderAPIKey:
    db.add(api_key)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(api_key)
    return api_key


def delete_provider_key(db: Session, *, api_key: ProviderAPIKey) -> None:
    db.delete(api_key)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


__all__ = [
    "create_provider_key",
    "delete_provider_key",
    "find_key_by_label",
    "get_provider_key_by_id",
    "list_provider_keys",
    "list_provider_keys_plain",
    "persist_provider_key",
]

