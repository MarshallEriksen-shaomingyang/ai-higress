"""
厂商API密钥管理路由 - V2版本，使用JWT认证
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Provider, ProviderAPIKey
from app.schemas import (
    ProviderAPIKeyCreateRequest,
    ProviderAPIKeyResponse,
    ProviderAPIKeyUpdateRequest,
)
from app.services.provider_key_service import (
    DuplicateProviderKeyLabelError,
    InvalidProviderKeyError,
    ProviderKeyServiceError,
    ProviderNotFoundError,
    create_provider_key,
    delete_provider_key,
    get_plaintext_key,
    get_provider_key_by_id,
    list_provider_keys,
    update_provider_key,
)

router = APIRouter(
    tags=["provider-keys"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_can_manage_provider_keys(
    db: Session,
    provider_id: str,
    current_user: AuthenticatedUser,
) -> None:
    """
    确保当前用户有权限管理指定 Provider 的上游 API 密钥。

    - 超级管理员：可以管理所有 Provider；
    - 普通用户：仅能管理自己私有/受限 Provider 的密钥（owner_id 匹配且 visibility 为 private/restricted）。
    """
    # 超级管理员直接放行
    if current_user.is_superuser:
        return

    # 查找 Provider 记录
    provider = (
        db.execute(select(Provider).where(Provider.provider_id == provider_id))
        .scalars()
        .first()
    )
    if provider is None:
        raise not_found(f"Provider {provider_id} not found")

    # 仅允许该私有 Provider 的所有者管理密钥
    if getattr(provider, "visibility", "public") in {"private", "restricted"} and (
        provider.owner_id is not None and str(provider.owner_id) == current_user.id
    ):
        return

    raise forbidden("只有提供商所有者或超级管理员可以管理此提供商的 API 密钥")


def _handle_provider_key_service_error(exc: ProviderKeyServiceError):
    """处理厂商密钥服务错误"""
    if isinstance(exc, ProviderNotFoundError):
        raise not_found(str(exc))
    elif isinstance(exc, InvalidProviderKeyError):
        raise bad_request(str(exc))
    elif isinstance(exc, DuplicateProviderKeyLabelError):
        raise bad_request(str(exc))
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {exc!s}",
        )


def _build_provider_key_response(key: ProviderAPIKey) -> ProviderAPIKeyResponse:
    """
    将数据库中的 ProviderAPIKey 实体转换为响应模型，并附带安全的密钥前缀。

    - 仅返回前缀信息（例如前 8 位 + 掩码），不会泄露完整密钥；
    - 当解密失败时，前缀字段为空，其他字段照常返回。
    """
    key_prefix: str | None = None
    try:
        plaintext = get_plaintext_key(key)
    except ProviderKeyServiceError:
        plaintext = ""

    if plaintext:
        # 最多展示前 8 个字符，其余用 * 掩码，避免泄露完整密钥。
        visible = plaintext[:8]
        key_prefix = visible + ("****" if len(plaintext) > len(visible) else "")

    resp = ProviderAPIKeyResponse.model_validate(key)
    # BaseModel 默认可变，这里直接补上 key_prefix 字段即可。
    resp.key_prefix = key_prefix
    return resp


@router.get(
    "/providers/{provider_id}/keys",
    response_model=list[ProviderAPIKeyResponse],
)
def list_provider_keys_endpoint(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderAPIKeyResponse]:
    """
    列出指定厂商的所有API密钥
    
    Args:
        provider_id: 厂商ID
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        厂商API密钥列表
    """
    _ensure_can_manage_provider_keys(db, provider_id, current_user)

    try:
        keys = list_provider_keys(db, provider_id)
        return [_build_provider_key_response(key) for key in keys]
    except ProviderKeyServiceError as exc:
        _handle_provider_key_service_error(exc)


@router.post(
    "/providers/{provider_id}/keys",
    response_model=ProviderAPIKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provider_key_endpoint(
    provider_id: str,
    payload: ProviderAPIKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderAPIKeyResponse:
    """
    创建新的厂商API密钥
    
    Args:
        provider_id: 厂商ID
        payload: 创建请求
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        新创建的厂商API密钥
    """
    _ensure_can_manage_provider_keys(db, provider_id, current_user)

    try:
        key = create_provider_key(db, provider_id, payload)
        return _build_provider_key_response(key)
    except ProviderKeyServiceError as exc:
        _handle_provider_key_service_error(exc)


@router.get(
    "/providers/{provider_id}/keys/{key_id}",
    response_model=ProviderAPIKeyResponse,
)
def get_provider_key_endpoint(
    provider_id: str,
    key_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderAPIKeyResponse:
    """
    获取指定的厂商API密钥
    
    Args:
        provider_id: 厂商ID
        key_id: 密钥ID
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        厂商API密钥
    """
    _ensure_can_manage_provider_keys(db, provider_id, current_user)

    try:
        key = get_provider_key_by_id(db, provider_id, key_id)
        if not key:
            raise not_found(f"Provider key {key_id} not found")
        return _build_provider_key_response(key)
    except ProviderKeyServiceError as exc:
        _handle_provider_key_service_error(exc)


@router.put(
    "/providers/{provider_id}/keys/{key_id}",
    response_model=ProviderAPIKeyResponse,
)
def update_provider_key_endpoint(
    provider_id: str,
    key_id: str,
    payload: ProviderAPIKeyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderAPIKeyResponse:
    """
    更新厂商API密钥
    
    Args:
        provider_id: 厂商ID
        key_id: 密钥ID
        payload: 更新请求
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        更新后的厂商API密钥
    """
    _ensure_can_manage_provider_keys(db, provider_id, current_user)

    try:
        key = update_provider_key(db, provider_id, key_id, payload)
        return _build_provider_key_response(key)
    except ProviderKeyServiceError as exc:
        _handle_provider_key_service_error(exc)


@router.delete(
    "/providers/{provider_id}/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_provider_key_endpoint(
    provider_id: str,
    key_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    """
    删除厂商API密钥
    
    Args:
        provider_id: 厂商ID
        key_id: 密钥ID
        db: 数据库会话
        current_user: 当前认证用户
    """
    _ensure_can_manage_provider_keys(db, provider_id, current_user)

    try:
        delete_provider_key(db, provider_id, key_id)
    except ProviderKeyServiceError as exc:
        _handle_provider_key_service_error(exc)


__all__ = ["router"]
