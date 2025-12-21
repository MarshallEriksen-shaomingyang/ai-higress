"""用户提供商管理路由 - 包括私有提供商和可用提供商列表"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Provider
from app.schemas.provider import ProviderResponse
from app.schemas.provider_control import (
    UserProviderCreateRequest,
    UserProviderUpdateRequest,
)
from app.services.user_permission_service import UserPermissionService
from app.services.user_provider_service import (
    UserProviderNotFoundError,
    UserProviderServiceError,
    count_user_private_providers,
    create_private_provider,
    get_private_provider_by_id,
    list_private_providers,
    list_providers_shared_with_user,
    update_private_provider,
)

router = APIRouter(
    tags=["user-providers"],
    dependencies=[Depends(require_jwt_token)],
)


@router.get(
    "/users/{user_id}/providers",
    response_model=dict,
)
def list_user_available_providers(
    user_id: UUID,
    visibility: str | None = Query(
        default=None,
        description="过滤可见性：all(全部) | private(仅私有) | public(仅公共) | shared(仅被授权)",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict:
    """获取用户可用的提供商列表（私有 + 公共）。
    
    - 用户只能查看自己的提供商列表（除非是超级管理员）
    - 返回用户的私有提供商和系统的公共提供商
    - 可通过 visibility 参数过滤
    """

    # 权限检查：只能查看自己的提供商列表
    if str(user_id) != current_user.id and not current_user.is_superuser:
        raise forbidden("无权查看其他用户的提供商列表")

    # 获取用户的私有提供商
    private_providers = []
    if visibility in (None, "all", "private"):
        private_providers = list_private_providers(db, user_id)

    shared_providers = []
    if visibility in (None, "all", "shared"):
        shared_providers = list_providers_shared_with_user(db, user_id)

    # 获取公共提供商
    public_providers = []
    if visibility in (None, "all", "public"):
        stmt = select(Provider).where(
            Provider.visibility == "public",
            Provider.owner_id.is_(None),
        )
        public_providers = list(db.execute(stmt).scalars().all())

    # 转换为响应格式
    private_list = [ProviderResponse.model_validate(p) for p in private_providers]
    shared_list = [
        ProviderResponse.model_validate(p, update={"shared_user_ids": None})
        for p in shared_providers
    ]
    public_list = [
        ProviderResponse.model_validate(p, update={"shared_user_ids": None})
        for p in public_providers
    ]

    return {
        "private_providers": private_list,
        "shared_providers": shared_list,
        "public_providers": public_list,
        "total": len(private_list) + len(shared_list) + len(public_list),
    }


@router.get(
    "/users/{user_id}/private-providers",
    response_model=list[ProviderResponse],
)
def list_user_private_providers_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderResponse]:
    """获取用户的私有提供商列表。"""

    # 权限检查
    if str(user_id) != current_user.id and not current_user.is_superuser:
        raise forbidden("无权查看其他用户的私有提供商")

    providers = list_private_providers(db, user_id)
    return [ProviderResponse.model_validate(p) for p in providers]


@router.post(
    "/users/{user_id}/private-providers",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_private_provider_endpoint(
    user_id: UUID,
    payload: UserProviderCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderResponse:
    """创建用户私有提供商。"""

    # 权限检查
    if str(user_id) != current_user.id and not current_user.is_superuser:
        raise forbidden("无权为其他用户创建私有提供商")

    # 检查创建权限
    perm = UserPermissionService(db)
    if not perm.has_permission(user_id, "create_private_provider"):
        raise forbidden("当前用户未被授权创建私有提供商")

    # 检查配额限制
    current_count = count_user_private_providers(db, user_id)
    # TODO: 从配置或用户权限中获取限制
    max_limit = 10  # 默认限制
    if current_count >= max_limit:
        raise bad_request(f"已达到私有提供商数量限制（{max_limit}）")

    try:
        provider = create_private_provider(db, user_id, payload)
        return ProviderResponse.model_validate(provider)
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))


@router.put(
    "/users/{user_id}/private-providers/{provider_id}",
    response_model=ProviderResponse,
)
def update_user_private_provider_endpoint(
    user_id: UUID,
    provider_id: str,
    payload: UserProviderUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderResponse:
    """更新用户私有提供商。"""

    # 权限检查
    if str(user_id) != current_user.id and not current_user.is_superuser:
        raise forbidden("无权修改其他用户的私有提供商")

    try:
        provider = update_private_provider(db, user_id, provider_id, payload)
        return ProviderResponse.model_validate(provider)
    except UserProviderNotFoundError:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))


@router.delete(
    "/users/{user_id}/private-providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user_private_provider_endpoint(
    user_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    """删除用户私有提供商。"""

    # 权限检查
    if str(user_id) != current_user.id and not current_user.is_superuser:
        raise forbidden("无权删除其他用户的私有提供商")

    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    db.delete(provider)
    db.commit()


__all__ = ["router"]
