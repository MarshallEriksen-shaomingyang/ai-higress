from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import forbidden
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import UserPermissionGrantRequest, UserPermissionResponse
from app.services.user_permission_service import UserPermissionService

router = APIRouter(
    tags=["admin-user-permissions"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


@router.get(
    "/admin/users/{user_id}/permissions",
    response_model=list[UserPermissionResponse],
)
def get_user_permissions_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[UserPermissionResponse]:
    """管理员查询指定用户的权限记录。"""

    _ensure_admin(current_user)
    service = UserPermissionService(db)
    records = service.get_user_permissions(user_id)
    return [UserPermissionResponse.model_validate(rec) for rec in records]


@router.post(
    "/admin/users/{user_id}/permissions",
    response_model=UserPermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_user_permission_endpoint(
    user_id: UUID,
    payload: UserPermissionGrantRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserPermissionResponse:
    """管理员授予或更新用户的某项权限。"""

    _ensure_admin(current_user)
    service = UserPermissionService(db)
    record = service.grant_permission(
        user_id=user_id,
        permission_type=payload.permission_type,
        permission_value=payload.permission_value,
        expires_at=payload.expires_at,
        notes=payload.notes,
    )
    return UserPermissionResponse.model_validate(record)


@router.delete(
    "/admin/users/{user_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_user_permission_endpoint(
    user_id: UUID,
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    """管理员撤销一条用户权限记录。"""

    _ensure_admin(current_user)
    service = UserPermissionService(db)
    # 简单检查：如果记录不存在直接返回 204
    records = service.get_user_permissions(user_id)
    if not any(str(r.id) == str(permission_id) for r in records):
        return
    service.revoke_permission(permission_id)


__all__ = ["router"]

