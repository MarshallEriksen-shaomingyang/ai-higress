from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Provider, ProviderAllowedUser


def get_provider_by_provider_id(db: Session, *, provider_id: str) -> Provider | None:
    stmt: Select[tuple[Provider]] = select(Provider).where(Provider.provider_id == provider_id)
    return db.execute(stmt).scalars().first()


def get_provider_by_uuid(db: Session, *, provider_uuid: object) -> Provider | None:
    try:
        return db.get(Provider, provider_uuid)
    except Exception:
        return None


def provider_id_exists(db: Session, *, provider_id: str) -> bool:
    stmt = select(Provider.id).where(Provider.provider_id == provider_id).limit(1)
    return db.execute(stmt).first() is not None


def count_user_private_providers(db: Session, *, owner_id: object) -> int:
    stmt = (
        select(func.count())
        .select_from(Provider)
        .where(
            Provider.owner_id == owner_id,
            Provider.visibility.in_(("private", "restricted")),
        )
    )
    return int(db.execute(stmt).scalar_one() or 0)


def list_public_provider_ids(db: Session) -> set[str]:
    stmt = select(Provider.provider_id).where(
        Provider.visibility == "public",
        Provider.owner_id.is_(None),
    )
    return set(db.execute(stmt).scalars().all())


def list_private_provider_ids_for_user(db: Session, *, user_id: object) -> set[str]:
    stmt = select(Provider.provider_id).where(Provider.owner_id == user_id)
    return set(db.execute(stmt).scalars().all())


def list_shared_provider_ids_for_user(db: Session, *, user_id: object) -> set[str]:
    stmt = (
        select(Provider.provider_id)
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
    return set(db.execute(stmt).scalars().all())


__all__ = [
    "count_user_private_providers",
    "get_provider_by_provider_id",
    "get_provider_by_uuid",
    "list_private_provider_ids_for_user",
    "list_public_provider_ids",
    "list_shared_provider_ids_for_user",
    "provider_id_exists",
]

