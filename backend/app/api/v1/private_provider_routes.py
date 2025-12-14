from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.errors import bad_request, forbidden, not_found
from app.logging_config import logger
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    ProviderSubmissionRequest,
    ProviderSubmissionResponse,
    UserProviderCreateRequest,
    UserProviderResponse,
    UserProviderUpdateRequest,
    UserQuotaResponse,
    ProviderSharedUsersResponse,
    ProviderSharedUsersUpdateRequest,
)
from app.services.encryption import decrypt_secret
from app.services.provider_submission_service import (
    ProviderSubmissionServiceError,
    create_submission,
)
from app.services.provider_validation_service import ProviderValidationService
from app.services.user_permission_service import UserPermissionService
from app.services.user_provider_service import (
    UserProviderNotFoundError,
    UserProviderServiceError,
    count_user_private_providers,
    create_private_provider,
    get_private_provider_by_id,
    list_private_providers,
    update_private_provider,
    update_provider_shared_users,
)
from app.settings import settings

router = APIRouter(
    tags=["user-providers"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_can_manage_user(current: AuthenticatedUser, target_user_id: UUID) -> None:
    if current.is_superuser:
        return
    if current.id != str(target_user_id):
        raise forbidden("无权管理其他用户的私有提供商")


@router.get(
    "/users/{user_id}/quota",
    response_model=UserQuotaResponse,
)
def get_user_quota_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserQuotaResponse:
    """
    获取指定用户的私有 Provider 配额信息。

    - 仅支持本人或超级管理员查询；
    - `private_provider_limit` 为展示用上限值；
    - 对于超级管理员或拥有 `unlimited_providers` 权限的用户，会返回 `is_unlimited=True`，
      此时 `private_provider_limit` 仅作为前端展示建议值，后端不会做硬性限制。
    """

    _ensure_can_manage_user(current_user, user_id)

    perm = UserPermissionService(db)
    raw_limit = perm.get_provider_limit(user_id)
    is_unlimited = raw_limit is None
    # 对于无限制用户，给出一个合理的展示上限，避免前端进度条失真
    display_limit = (
        settings.max_user_private_provider_limit
        if is_unlimited
        else int(raw_limit)
    )

    current_count = count_user_private_providers(db, user_id)

    return UserQuotaResponse(
        private_provider_limit=display_limit,
        private_provider_count=current_count,
        is_unlimited=is_unlimited,
    )


@router.post(
    "/users/{user_id}/private-providers",
    response_model=UserProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_private_provider_endpoint(
    user_id: UUID,
    payload: UserProviderCreateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProviderResponse:
    """为指定用户创建一个私有提供商，仅该用户的 API Key 可选择使用。"""

    _ensure_can_manage_user(current_user, user_id)

    perm = UserPermissionService(db)
    if not perm.has_permission(user_id, "create_private_provider"):
        raise forbidden("当前用户未被授予创建私有提供商的权限")

    limit = perm.get_provider_limit(user_id)
    if limit is not None:
        current_count = count_user_private_providers(db, user_id)
        if current_count >= limit:
            raise forbidden(f"已达到私有提供商数量限制（{limit}）")

    try:
        provider = create_private_provider(db, user_id, payload)
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))

    # 失效逻辑模型缓存，下次查询时会从数据库回源
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys after creating provider %s", deleted, provider.provider_id)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")

    return UserProviderResponse.model_validate(provider)


@router.get(
    "/users/{user_id}/private-providers",
    response_model=list[UserProviderResponse],
)
def list_private_providers_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[UserProviderResponse]:
    """获取用户的私有提供商列表。"""

    _ensure_can_manage_user(current_user, user_id)
    providers = list_private_providers(db, user_id)
    return [UserProviderResponse.model_validate(p) for p in providers]


@router.put(
    "/users/{user_id}/private-providers/{provider_id}",
    response_model=UserProviderResponse,
)
async def update_private_provider_endpoint(
    user_id: UUID,
    provider_id: str,
    payload: UserProviderUpdateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProviderResponse:
    """更新用户的私有提供商配置。"""

    _ensure_can_manage_user(current_user, user_id)

    try:
        provider = update_private_provider(db, user_id, provider_id, payload)
    except UserProviderNotFoundError:
        raise not_found(f"Private provider '{provider_id}' not found")
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))

    # 失效逻辑模型缓存，下次查询时会从数据库回源
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys after updating provider %s", deleted, provider_id)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")

    return UserProviderResponse.model_validate(provider)


@router.get(
    "/users/{user_id}/private-providers/{provider_id}/shared-users",
    response_model=ProviderSharedUsersResponse,
)
def list_provider_shared_users_endpoint(
    user_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSharedUsersResponse:
    """查询私有 Provider 的授权用户列表。"""

    _ensure_can_manage_user(current_user, user_id)

    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"Private provider '{provider_id}' not found")

    shared_ids = [link.user_id for link in provider.shared_users]
    return ProviderSharedUsersResponse(
        provider_id=provider.provider_id,
        visibility=provider.visibility,
        shared_user_ids=shared_ids,
    )


@router.put(
    "/users/{user_id}/private-providers/{provider_id}/shared-users",
    response_model=ProviderSharedUsersResponse,
)
def update_provider_shared_users_endpoint(
    user_id: UUID,
    provider_id: str,
    payload: ProviderSharedUsersUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSharedUsersResponse:
    """设置或清空私有 Provider 的授权用户列表。"""

    _ensure_can_manage_user(current_user, user_id)

    try:
        provider = update_provider_shared_users(
            db, user_id, provider_id, payload.user_ids
        )
    except UserProviderNotFoundError:
        raise not_found(f"Private provider '{provider_id}' not found")
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))

    shared_ids = [link.user_id for link in provider.shared_users]
    return ProviderSharedUsersResponse(
        provider_id=provider.provider_id,
        visibility=provider.visibility,
        shared_user_ids=shared_ids,
    )


@router.post(
    "/users/{user_id}/private-providers/{provider_id}/submit-shared",
    response_model=ProviderSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_private_provider_to_shared_pool_endpoint(
    user_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSubmissionResponse:
    """
    将用户的私有 Provider 一键提交到共享池，进入管理员审核流程。

    - 仅允许本人或超级管理员操作；
    - 需要具备 `submit_shared_provider` 权限；
    - 会从对应私有 Provider 上选择一条启用中的上游 API 密钥进行验证；
    - 验证通过后创建一条 ProviderSubmission 记录，状态为 pending。
    """

    # 只能操作自己的私有 Provider
    _ensure_can_manage_user(current_user, user_id)

    perm = UserPermissionService(db)
    if not perm.has_permission(user_id, "submit_shared_provider"):
        raise forbidden("当前用户未被授予提交共享提供商的权限")

    # 查找对应的私有 Provider（确保 owner_id/visibility 匹配）
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    # 从 Provider 的上游密钥中挑选一条启用中的密钥
    active_key = next(
        (k for k in provider.api_keys if getattr(k, "status", "") == "active"),
        None,
    )
    if active_key is None:
        raise bad_request("当前私有提供商未配置可用的上游 API 密钥")

    # 解密上游 API Key
    try:
        api_key_plain = decrypt_secret(active_key.encrypted_key)
    except ValueError:
        raise bad_request("无法解密上游 API 密钥，请联系管理员")

    # 复用 ProviderValidationService 做连通性验证
    validator = ProviderValidationService()
    validation = await validator.validate_provider_config(
        provider.base_url,
        api_key_plain,
        provider.provider_type,
    )
    if not validation.is_valid:
        raise bad_request(f"提供商配置验证失败: {validation.error_message or '未知错误'}")

    # 构造提交请求 payload，并创建提交记录
    payload = ProviderSubmissionRequest(
        name=provider.name,
        provider_id=provider.provider_id,
        base_url=provider.base_url,
        provider_type=provider.provider_type or "native",
        api_key=api_key_plain,
    )

    try:
        submission = create_submission(
            db,
            user_id,
            payload,
            metadata=validation.metadata,
        )
    except ProviderSubmissionServiceError as exc:
        raise bad_request(str(exc))

    return ProviderSubmissionResponse.model_validate(submission)


__all__ = ["router"]
