from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.services.jwt_auth_service import hash_password, verify_password


class UserServiceError(Exception):
    """Base error for the user service layer."""


class UsernameAlreadyExistsError(UserServiceError):
    """Raised when the username is already taken."""


class EmailAlreadyExistsError(UserServiceError):
    """Raised when the email already belongs to another user."""


def _record_exists(
    session: Session,
    stmt: Select[tuple[User]],
) -> bool:
    return session.execute(stmt).scalars().first() is not None


def _username_exists(
    session: Session, username: str, *, exclude_user_id: UUID | None = None
) -> bool:
    stmt = select(User).where(User.username == username)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return _record_exists(session, stmt)


def _email_exists(
    session: Session, email: str, *, exclude_user_id: UUID | None = None
) -> bool:
    stmt = select(User).where(User.email == email)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return _record_exists(session, stmt)


def get_user_by_id(session: Session, user_id: UUID | str) -> User | None:
    """Return a user by primary key."""

    if isinstance(user_id, str):
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return None
    else:
        user_uuid = user_id
    return session.get(User, user_uuid)


def create_user(
    session: Session,
    payload: UserCreateRequest,
    *,
    is_superuser: bool = False,
    is_active: bool = True,
) -> User:
    """Create a new user after checking for unique username/email."""

    # 检查邮箱唯一性
    if _email_exists(session, payload.email):
        raise EmailAlreadyExistsError("email already in use")
    
    # 如果提供了用户名，检查用户名唯一性
    username = payload.username
    if username is not None:
        if _username_exists(session, username):
            raise UsernameAlreadyExistsError("username already in use")
    else:
        # 如果没有提供用户名，根据邮箱自动生成
        username_prefix = payload.email.split("@")[0]
        # 确保用户名唯一性
        existing_user = session.execute(select(User).where(User.username == username_prefix)).scalar_one_or_none()
        
        # 如果存在，添加数字后缀
        counter = 1
        username = username_prefix
        while existing_user is not None:
            username = f"{username_prefix}{counter}"
            existing_user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
            counter += 1

    user = User(
        username=username,
        email=payload.email,
        display_name=payload.display_name,
        avatar=payload.avatar,
        hashed_password=hash_password(payload.password),
        is_superuser=is_superuser,
        is_active=is_active,
    )

    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover - safety net for rare races
        session.rollback()
        raise UserServiceError("Failed to create user") from exc
    session.refresh(user)
    return user


def update_user(session: Session, user: User, payload: UserUpdateRequest) -> User:
    """Update mutable profile fields and password for a user."""

    if payload.email is not None and payload.email != user.email:
        if _email_exists(session, payload.email, exclude_user_id=user.id):
            raise EmailAlreadyExistsError("email already in use")
        user.email = payload.email

    if payload.display_name is not None:
        user.display_name = payload.display_name

    if payload.avatar is not None:
        user.avatar = payload.avatar

    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)

    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover - safety net for rare races
        session.rollback()
        raise UserServiceError("Failed to update user") from exc
    session.refresh(user)
    return user


def set_user_active(
    session: Session, user: User, *, is_active: bool
) -> tuple[User, list[str]]:
    """Toggle whether a user is active and return related API key hashes."""

    user.is_active = is_active
    session.add(user)
    session.commit()
    session.refresh(user)

    key_hashes = [key.key_hash for key in user.api_keys]
    return user, key_hashes


def has_any_user(session: Session) -> bool:
    """Return whether at least one user already exists."""

    stmt = select(User.id).limit(1)
    return session.execute(stmt).first() is not None


__all__ = [
    "EmailAlreadyExistsError",
    "has_any_user",
    "UserServiceError",
    "UsernameAlreadyExistsError",
    "create_user",
    "get_user_by_id",
    "set_user_active",
    "update_user",
]
