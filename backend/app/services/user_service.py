from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_repository import (
    create_user as repo_create_user,
    email_exists as repo_email_exists,
    find_unique_username as repo_find_unique_username,
    get_user_by_id as repo_get_user_by_id,
    has_any_user as repo_has_any_user,
    persist_user as repo_persist_user,
    set_user_active_and_list_key_hashes as repo_set_user_active_and_list_key_hashes,
    username_exists as repo_username_exists,
)
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.services.credit_service import get_or_create_account_for_user
from app.services.jwt_auth_service import hash_password
from app.services.registration_window_service import (
    claim_registration_slot,
    rollback_registration_slot,
)
from app.services.role_service import RoleCodeAlreadyExistsError, RoleService


class UserServiceError(Exception):
    """Base error for the user service layer."""


class UsernameAlreadyExistsError(UserServiceError):
    """Raised when the username is already taken."""


class EmailAlreadyExistsError(UserServiceError):
    """Raised when the email already belongs to another user."""


DEFAULT_USER_ROLE_CODE = "default_user"


def assign_default_role(
    session: Session,
    user_id: UUID,
    *,
    role_code: str = DEFAULT_USER_ROLE_CODE,
) -> None:
    """为新用户分配默认角色（若不存在则自动创建）。"""

    service = RoleService(session)
    role = service.get_role_by_code(role_code)
    if role is None:
        try:
            role = service.create_role(
                code=role_code,
                name="默认用户",
                description="系统默认普通用户角色",
            )
        except RoleCodeAlreadyExistsError:
            # 并发场景下如果已经被其他进程创建，则重新查询
            role = service.get_role_by_code(role_code)
    if role is None:
        return

    service.set_user_roles(user_id, [role.id])


def _username_exists(
    session: Session, username: str, *, exclude_user_id: UUID | None = None
) -> bool:
    return repo_username_exists(session, username=username, exclude_user_id=exclude_user_id)


def _email_exists(
    session: Session, email: str, *, exclude_user_id: UUID | None = None
) -> bool:
    return repo_email_exists(session, email=email, exclude_user_id=exclude_user_id)


def get_user_by_id(session: Session, user_id: UUID | str) -> User | None:
    """Return a user by primary key."""
    return repo_get_user_by_id(session, user_id=user_id)


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
        username = repo_find_unique_username(session, base_username=username_prefix)

    user = User(
        username=username,
        email=payload.email,
        display_name=payload.display_name,
        avatar=payload.avatar,
        hashed_password=hash_password(payload.password),
        is_superuser=is_superuser,
        is_active=is_active,
    )
    try:
        user = repo_create_user(session, user=user)
    except IntegrityError as exc:  # pragma: no cover - safety net for rare races
        raise UserServiceError("Failed to create user") from exc
    return user


def register_user_with_window(
    session: Session, payload: UserCreateRequest
) -> tuple[User, bool]:
    """
    通过注册窗口创建用户，初始化积分账户和默认角色。

    返回 (user, requires_manual_activation)。
    """

    window = claim_registration_slot(session)

    try:
        user = create_user(
            session,
            payload,
            is_active=window.auto_activate,
        )
        get_or_create_account_for_user(session, user.id)
        assign_default_role(session, user.id)
    except (UsernameAlreadyExistsError, EmailAlreadyExistsError):
        rollback_registration_slot(session, window.id)
        raise
    except Exception:
        rollback_registration_slot(session, window.id)
        raise

    return user, not window.auto_activate


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

    try:
        user = repo_persist_user(session, user=user)
    except IntegrityError as exc:  # pragma: no cover - safety net for rare races
        raise UserServiceError("Failed to update user") from exc
    return user


def set_user_active(
    session: Session, user: User, *, is_active: bool
) -> tuple[User, list[str]]:
    """Toggle whether a user is active and return related API key hashes."""
    return repo_set_user_active_and_list_key_hashes(session, user=user, is_active=is_active)


def has_any_user(session: Session) -> bool:
    """Return whether at least one user already exists."""
    return repo_has_any_user(session)


__all__ = [
    "DEFAULT_USER_ROLE_CODE",
    "EmailAlreadyExistsError",
    "UserServiceError",
    "UsernameAlreadyExistsError",
    "assign_default_role",
    "create_user",
    "get_user_by_id",
    "has_any_user",
    "register_user_with_window",
    "set_user_active",
    "update_user",
]
