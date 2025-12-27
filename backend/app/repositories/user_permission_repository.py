from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models import Permission, RolePermission, UserPermission, UserRole


def has_direct_permission(
    db: Session,
    *,
    user_id: UUID,
    permission_type: str,
    now: datetime,
) -> bool:
    stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
        UserPermission.user_id == user_id,
        UserPermission.permission_type == permission_type,
        or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
    )
    return db.execute(stmt).scalars().first() is not None


def has_role_permission(db: Session, *, user_id: UUID, permission_code: str) -> bool:
    stmt = (
        select(RolePermission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.user_id == user_id, Permission.code == permission_code)
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def list_all_permission_codes(db: Session) -> list[str]:
    stmt = select(Permission.code)
    return list(db.execute(stmt).scalars().all())


def list_direct_permission_types(db: Session, *, user_id: UUID, now: datetime) -> set[str]:
    stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
        UserPermission.user_id == user_id,
        or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
    )
    records = list(db.execute(stmt).scalars().all())
    return {rec.permission_type for rec in records}


def list_role_permission_codes(db: Session, *, user_id: UUID) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    return set(db.execute(stmt).scalars().all())


def list_user_permissions(db: Session, *, user_id: UUID) -> list[UserPermission]:
    stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
        UserPermission.user_id == user_id
    )
    return list(db.execute(stmt).scalars().all())


def get_user_permission_by_type(
    db: Session,
    *,
    user_id: UUID,
    permission_type: str,
) -> UserPermission | None:
    stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
        UserPermission.user_id == user_id,
        UserPermission.permission_type == permission_type,
    )
    return db.execute(stmt).scalars().first()


def upsert_user_permission(
    db: Session,
    *,
    user_id: UUID,
    permission_type: str,
    permission_value: str | None,
    expires_at: datetime | None,
    notes: str | None,
) -> UserPermission:
    record = get_user_permission_by_type(db, user_id=user_id, permission_type=permission_type)
    if record is None:
        record = UserPermission(
            user_id=user_id,
            permission_type=permission_type,
            permission_value=permission_value,
            expires_at=expires_at,
            notes=notes,
        )
        db.add(record)
    else:
        record.permission_value = permission_value
        record.expires_at = expires_at
        if notes is not None:
            record.notes = notes
    db.commit()
    db.refresh(record)
    return record


def delete_user_permission(db: Session, *, permission_id: UUID) -> None:
    record = db.get(UserPermission, permission_id)
    if record is None:
        return
    db.delete(record)
    db.commit()


def has_unlimited_providers(db: Session, *, user_id: UUID, now: datetime) -> bool:
    stmt = select(UserPermission.id).where(
        UserPermission.user_id == user_id,
        UserPermission.permission_type == "unlimited_providers",
        or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
    ).limit(1)
    return db.execute(stmt).first() is not None


def get_private_provider_limit_record(
    db: Session,
    *,
    user_id: UUID,
    now: datetime,
) -> UserPermission | None:
    stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
        UserPermission.user_id == user_id,
        UserPermission.permission_type == "private_provider_limit",
        or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
    )
    return db.execute(stmt).scalars().first()


__all__ = [
    "delete_user_permission",
    "get_private_provider_limit_record",
    "has_direct_permission",
    "has_role_permission",
    "has_unlimited_providers",
    "list_all_permission_codes",
    "list_direct_permission_types",
    "list_role_permission_codes",
    "list_user_permissions",
    "upsert_user_permission",
]

