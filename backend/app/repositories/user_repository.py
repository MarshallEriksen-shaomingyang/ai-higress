from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import APIKey, User


def username_exists(db: Session, *, username: str, exclude_user_id: UUID | None = None) -> bool:
    stmt: Select[tuple[User]] = select(User).where(User.username == username)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return db.execute(stmt).scalars().first() is not None


def email_exists(db: Session, *, email: str, exclude_user_id: UUID | None = None) -> bool:
    stmt: Select[tuple[User]] = select(User).where(User.email == email)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return db.execute(stmt).scalars().first() is not None


def get_user_by_id(db: Session, *, user_id: UUID | str) -> User | None:
    if isinstance(user_id, str):
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return None
    else:
        user_uuid = user_id
    return db.get(User, user_uuid)


def has_any_user(db: Session) -> bool:
    stmt = select(User.id).limit(1)
    return db.execute(stmt).first() is not None


def find_unique_username(db: Session, *, base_username: str) -> str:
    base = (base_username or "").strip()
    if not base:
        base = "user"

    candidate = base
    counter = 1
    while username_exists(db, username=candidate):
        candidate = f"{base}{counter}"
        counter += 1
        if counter > 1000:
            # 极端保护：避免死循环
            raise RuntimeError("failed to allocate unique username")
    return candidate


def create_user(db: Session, *, user: User) -> User:
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user


def persist_user(db: Session, *, user: User) -> User:
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user


def set_user_active_and_list_key_hashes(
    db: Session,
    *,
    user: User,
    is_active: bool,
) -> tuple[User, list[str]]:
    user.is_active = bool(is_active)
    db.add(user)
    db.commit()
    db.refresh(user)

    stmt = select(APIKey.key_hash).where(APIKey.user_id == user.id)
    key_hashes = list(db.execute(stmt).scalars().all())
    return user, key_hashes


__all__ = [
    "create_user",
    "email_exists",
    "find_unique_username",
    "get_user_by_id",
    "has_any_user",
    "persist_user",
    "set_user_active_and_list_key_hashes",
    "username_exists",
]

