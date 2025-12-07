from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import forbidden
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import User
from app.schemas.user import UserPermissionFlag, UserResponse
from app.services.avatar_service import build_avatar_url
from app.services.role_service import RoleService
from app.services.user_permission_service import UserPermissionService

router = APIRouter(
    tags=["admin-users"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


def _build_admin_user_response(
    role_service: RoleService,
    perm_service: UserPermissionService,
    user: User,
) -> UserResponse:
    """构造用于管理员视角的 UserResponse。"""

    roles = role_service.get_user_roles(user.id)
    role_codes = [r.code for r in roles]

    # 仅暴露当前界面需要关注的布尔能力标记，其余仍由后端在权限校验中处理
    can_create_private_provider = perm_service.has_permission(
        user.id, "create_private_provider"
    )
    can_submit_shared_provider = perm_service.has_permission(
        user.id, "submit_shared_provider"
    )
    permission_flags: list[UserPermissionFlag] = [
        UserPermissionFlag(
            key="can_create_private_provider",
            value=bool(can_create_private_provider),
        ),
        UserPermissionFlag(
            key="can_submit_shared_provider",
            value=bool(can_submit_shared_provider),
        ),
    ]

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar=build_avatar_url(user.avatar),
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_codes=role_codes,
        permission_flags=permission_flags,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get(
    "/admin/users",
    response_model=list[UserResponse],
)
def list_users_endpoint(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[UserResponse]:
    """
    管理员获取系统中所有用户的概要信息。

    前端用户管理页面会基于该接口展示用户列表、角色标签以及部分能力标记。
    """

    _ensure_admin(current_user)

    stmt: Select[tuple[User]] = select(User).order_by(User.created_at)
    users = list(db.execute(stmt).scalars().all())

    role_service = RoleService(db)
    perm_service = UserPermissionService(db)

    return [
        _build_admin_user_response(role_service, perm_service, user)
        for user in users
    ]


__all__ = ["router"]
