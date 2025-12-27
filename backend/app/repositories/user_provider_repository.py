from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Provider, ProviderAllowedUser, ProviderAPIKey


def provider_exists(db: Session, *, provider_id: str) -> bool:
    stmt = select(Provider.id).where(Provider.provider_id == provider_id).limit(1)
    return db.execute(stmt).first() is not None


def create_private_provider_with_key(
    db: Session,
    *,
    provider: Provider,
    encrypted_key: bytes,
    max_qps: int | None,
) -> Provider:
    db.add(provider)
    db.flush()  # ensure provider.id

    api_key = ProviderAPIKey(
        provider_uuid=provider.id,
        encrypted_key=encrypted_key,
        weight=1.0,
        max_qps=max_qps,
        label="default",
        status="active",
    )
    db.add(api_key)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(provider)
    return provider


def list_private_providers(db: Session, *, owner_id: UUID) -> list[Provider]:
    stmt: Select[tuple[Provider]] = select(Provider).where(
        Provider.owner_id == owner_id,
        Provider.visibility.in_(("private", "restricted")),
    )
    return list(db.execute(stmt).scalars().all())


def get_private_provider_by_id(
    db: Session,
    *,
    owner_id: UUID,
    provider_id: str,
) -> Provider | None:
    stmt: Select[tuple[Provider]] = select(Provider).where(
        Provider.owner_id == owner_id,
        Provider.visibility.in_(("private", "restricted")),
        Provider.provider_id == provider_id,
    )
    return db.execute(stmt).scalars().first()


def persist_provider(db: Session, *, provider: Provider) -> Provider:
    db.add(provider)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(provider)
    return provider


def count_user_private_providers(db: Session, *, owner_id: UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(Provider)
        .where(
            Provider.owner_id == owner_id,
            Provider.visibility.in_(("private", "restricted")),
        )
    )
    return int(db.execute(stmt).scalar_one() or 0)


def list_providers_shared_with_user(db: Session, *, user_id: UUID) -> list[Provider]:
    stmt: Select[tuple[Provider]] = (
        select(Provider)
        .join(
            ProviderAllowedUser,
            ProviderAllowedUser.provider_uuid == Provider.id,
        )
        .where(
            Provider.visibility == "restricted",
            ProviderAllowedUser.user_id == user_id,
            Provider.owner_id != user_id,
        )
    )
    return list(db.execute(stmt).scalars().all())


def get_accessible_provider_ids(db: Session, *, user_id: UUID, is_superuser: bool) -> set[str]:
    if is_superuser:
        stmt = select(Provider.provider_id)
        return set(db.execute(stmt).scalars().all())

    shared_exists = (
        select(ProviderAllowedUser.id)
        .where(
            ProviderAllowedUser.provider_uuid == Provider.id,
            ProviderAllowedUser.user_id == user_id,
        )
        .exists()
    )
    stmt = select(Provider.provider_id).where(
        or_(
            and_(Provider.visibility == "public", Provider.owner_id.is_(None)),
            Provider.owner_id == user_id,
            and_(Provider.visibility == "restricted", shared_exists),
        )
    )
    return set(db.execute(stmt).scalars().all())


def update_provider_shared_users(
    db: Session,
    *,
    provider: Provider,
    target_user_ids: Iterable[UUID],
) -> tuple[Provider, list[UUID]]:
    existing_map = {link.user_id: link for link in provider.shared_users}
    target_set = set(target_user_ids)
    added_user_ids = [uid for uid in target_set if uid not in existing_map]

    for link in list(provider.shared_users):
        if link.user_id not in target_set:
            provider.shared_users.remove(link)
            db.delete(link)

    for uid in target_set:
        if uid not in existing_map:
            provider.shared_users.append(
                ProviderAllowedUser(user_id=uid, provider_uuid=provider.id)
            )

    provider.visibility = "restricted" if target_set else "private"
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider, added_user_ids


__all__ = [
    "count_user_private_providers",
    "create_private_provider_with_key",
    "get_accessible_provider_ids",
    "get_private_provider_by_id",
    "list_private_providers",
    "list_providers_shared_with_user",
    "persist_provider",
    "provider_exists",
    "update_provider_shared_users",
]
