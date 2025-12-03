"""
用户管理路由 - V2版本，使用JWT认证
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_redis
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.services.api_key_cache import invalidate_cached_api_key
from app.services.user_service import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    create_user,
    get_user_by_id,
    set_user_active,
    update_user,
)

router = APIRouter(
    tags=["users"],
    dependencies=[Depends(require_jwt_token)],
)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user_endpoint(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """注册一个新用户并存储哈希密码。"""

    try:
        user = create_user(db, payload)
    except UsernameAlreadyExistsError:
        raise bad_request("用户名已存在")
    except EmailAlreadyExistsError:
        raise bad_request("邮箱已被使用")
    return UserResponse.model_validate(user)


@router.get("/users/me", response_model=UserResponse)
def get_current_user_endpoint(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """获取当前认证用户的信息。"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar=current_user.avatar,
        is_superuser=current_user.is_superuser,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """更新可编辑的用户资料字段和密码。"""
    
    # 检查权限：用户只能更新自己的信息，除非是超级用户
    if not current_user.is_superuser and current_user.id != str(user_id):
        raise forbidden("无权修改其他用户信息")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise not_found(f"User {user_id} not found")

    try:
        updated = update_user(db, user, payload)
    except EmailAlreadyExistsError:
        raise bad_request("邮箱已被使用")
    return UserResponse.model_validate(updated)


async def _invalidate_user_api_keys(redis, key_hashes: list[str]) -> None:
    for key_hash in key_hashes:
        await invalidate_cached_api_key(redis, key_hash)


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status_endpoint(
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """允许超级用户禁用/恢复用户，立即撤销其 API 密钥缓存。"""

    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以封禁用户")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise not_found(f"User {user_id} not found")

    updated, key_hashes = set_user_active(db, user, is_active=payload.is_active)
    await _invalidate_user_api_keys(redis, key_hashes)

    return UserResponse.model_validate(updated)


__all__ = ["router"]