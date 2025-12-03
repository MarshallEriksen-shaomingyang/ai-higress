"""
厂商API密钥管理路由 - V2版本，使用JWT认证
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
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
    get_provider_key_by_id,
    list_provider_keys,
    update_provider_key,
)

router = APIRouter(
    tags=["provider-keys"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_superuser(current_user: AuthenticatedUser) -> None:
    """确保当前用户是超级用户"""
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以管理厂商API密钥")


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
            detail=f"Internal error: {str(exc)}",
        )


@router.get(
    "/providers/{provider_id}/keys",
    response_model=List[ProviderAPIKeyResponse],
)
def list_provider_keys_endpoint(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> List[ProviderAPIKeyResponse]:
    """
    列出指定厂商的所有API密钥
    
    Args:
        provider_id: 厂商ID
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        厂商API密钥列表
    """
    _ensure_superuser(current_user)
    
    try:
        keys = list_provider_keys(db, provider_id)
        return [ProviderAPIKeyResponse.model_validate(key) for key in keys]
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
    _ensure_superuser(current_user)
    
    try:
        key = create_provider_key(db, provider_id, payload)
        return ProviderAPIKeyResponse.model_validate(key)
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
    _ensure_superuser(current_user)
    
    try:
        key = get_provider_key_by_id(db, provider_id, key_id)
        if not key:
            raise not_found(f"Provider key {key_id} not found")
        return ProviderAPIKeyResponse.model_validate(key)
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
    _ensure_superuser(current_user)
    
    try:
        key = update_provider_key(db, provider_id, key_id, payload)
        return ProviderAPIKeyResponse.model_validate(key)
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
    _ensure_superuser(current_user)
    
    try:
        delete_provider_key(db, provider_id, key_id)
    except ProviderKeyServiceError as exc:
        _handle_provider_key_service_error(exc)


__all__ = ["router"]