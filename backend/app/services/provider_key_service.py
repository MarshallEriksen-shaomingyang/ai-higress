"""
厂商API密钥管理服务
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.logging_config import logger
from app.models import Provider, ProviderAPIKey
from app.schemas import ProviderAPIKeyCreateRequest, ProviderAPIKeyUpdateRequest
from app.services.encryption import decrypt_secret, encrypt_secret


class ProviderKeyServiceError(Exception):
    """厂商密钥服务基础错误"""
    pass


class ProviderNotFoundError(ProviderKeyServiceError):
    """厂商不存在错误"""
    pass


class InvalidProviderKeyError(ProviderKeyServiceError):
    """无效的厂商密钥错误"""
    pass


class DuplicateProviderKeyLabelError(ProviderKeyServiceError):
    """厂商密钥标签重复错误"""
    pass


def _hash_provider_key(provider_id: str, raw_key: str) -> str:
    """
    为厂商密钥生成唯一标识符哈希
    
    Args:
        provider_id: 厂商ID
        raw_key: 原始密钥
        
    Returns:
        密钥哈希值
    """
    import hashlib
    import hmac
    from app.settings import settings
    
    secret = settings.secret_key.encode("utf-8")
    msg = f"{provider_id}:{raw_key}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def list_provider_keys(session: Session, provider_id: str) -> List[ProviderAPIKey]:
    """
    列出指定厂商的所有API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        
    Returns:
        厂商API密钥列表
        
    Raises:
        ProviderNotFoundError: 如果厂商不存在
    """
    # 检查厂商是否存在
    provider = session.get(Provider, provider_id)
    if not provider:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    
    stmt = select(ProviderAPIKey).where(ProviderAPIKey.provider_id == provider_id)
    return list(session.execute(stmt).scalars().all())


def get_provider_key_by_id(
    session: Session, 
    provider_id: str, 
    key_id: str
) -> Optional[ProviderAPIKey]:
    """
    根据ID获取厂商API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        key_id: 密钥ID
        
    Returns:
        厂商API密钥，如果不存在则返回None
        
    Raises:
        ProviderNotFoundError: 如果厂商不存在
    """
    # 检查厂商是否存在
    provider = session.get(Provider, provider_id)
    if not provider:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    
    return session.get(ProviderAPIKey, key_id)


def validate_provider_key(provider_id: str, raw_key: str) -> bool:
    """
    验证厂商API密钥是否有效
    
    Args:
        provider_id: 厂商ID
        raw_key: 原始密钥
        
    Returns:
        密钥是否有效
        
    Note:
        这里可以添加针对不同厂商的特定验证逻辑
    """
    if not raw_key or not raw_key.strip():
        return False
    
    # 这里可以添加针对特定厂商的验证逻辑
    # 例如，检查密钥格式是否符合特定厂商的要求
    
    return True


def create_provider_key(
    session: Session,
    provider_id: str,
    payload: ProviderAPIKeyCreateRequest,
) -> ProviderAPIKey:
    """
    创建新的厂商API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        payload: 创建请求
        
    Returns:
        新创建的厂商API密钥
        
    Raises:
        ProviderNotFoundError: 如果厂商不存在
        InvalidProviderKeyError: 如果密钥无效
        DuplicateProviderKeyLabelError: 如果密钥标签已存在
        ProviderKeyServiceError: 如果创建失败
    """
    # 检查厂商是否存在
    provider = session.get(Provider, provider_id)
    if not provider:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    
    # 验证密钥
    if not validate_provider_key(provider_id, payload.key):
        raise InvalidProviderKeyError(f"Invalid API key for provider {provider_id}")
    
    # 检查标签是否已存在
    existing = session.execute(
        select(ProviderAPIKey).where(
            ProviderAPIKey.provider_id == provider_id,
            ProviderAPIKey.label == payload.label,
        )
    ).scalars().first()
    
    if existing:
        raise DuplicateProviderKeyLabelError(f"Label '{payload.label}' already exists for provider {provider_id}")
    
    # 加密并创建密钥
    encrypted_key = encrypt_secret(payload.key)
    key_hash = _hash_provider_key(provider_id, payload.key)
    
    api_key = ProviderAPIKey(
        provider_id=provider_id,
        label=payload.label,
        encrypted_key=encrypted_key,
        key_hash=key_hash,
        weight=payload.weight,
        max_qps=payload.max_qps,
        status="active",
    )
    
    session.add(api_key)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ProviderKeyServiceError(f"Failed to create provider key: {exc}") from exc
    
    session.refresh(api_key)
    logger.info(f"Created new API key for provider {provider_id} with label {payload.label}")
    return api_key


def update_provider_key(
    session: Session,
    provider_id: str,
    key_id: str,
    payload: ProviderAPIKeyUpdateRequest,
) -> ProviderAPIKey:
    """
    更新厂商API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        key_id: 密钥ID
        payload: 更新请求
        
    Returns:
        更新后的厂商API密钥
        
    Raises:
        ProviderNotFoundError: 如果厂商不存在
        InvalidProviderKeyError: 如果密钥无效
        DuplicateProviderKeyLabelError: 如果密钥标签已存在
        ProviderKeyServiceError: 如果更新失败
    """
    # 检查厂商是否存在
    provider = session.get(Provider, provider_id)
    if not provider:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    
    # 获取密钥
    api_key = session.get(ProviderAPIKey, key_id)
    if not api_key or api_key.provider_id != provider_id:
        raise ProviderKeyServiceError(f"Provider key {key_id} not found for provider {provider_id}")
    
    # 如果提供了新密钥，则验证并更新
    if payload.key:
        if not validate_provider_key(provider_id, payload.key):
            raise InvalidProviderKeyError(f"Invalid API key for provider {provider_id}")
        
        api_key.encrypted_key = encrypt_secret(payload.key)
        api_key.key_hash = _hash_provider_key(provider_id, payload.key)
    
    # 检查标签是否与其他密钥冲突
    if payload.label and payload.label != api_key.label:
        existing = session.execute(
            select(ProviderAPIKey).where(
                ProviderAPIKey.provider_id == provider_id,
                ProviderAPIKey.label == payload.label,
                ProviderAPIKey.id != key_id,
            )
        ).scalars().first()
        
        if existing:
            raise DuplicateProviderKeyLabelError(f"Label '{payload.label}' already exists for provider {provider_id}")
        
        api_key.label = payload.label
    
    # 更新其他字段
    if payload.weight is not None:
        api_key.weight = payload.weight
    
    if payload.max_qps is not None:
        api_key.max_qps = payload.max_qps
    
    if payload.status is not None:
        api_key.status = payload.status
    
    session.add(api_key)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ProviderKeyServiceError(f"Failed to update provider key: {exc}") from exc
    
    session.refresh(api_key)
    logger.info(f"Updated API key {key_id} for provider {provider_id}")
    return api_key


def delete_provider_key(
    session: Session,
    provider_id: str,
    key_id: str,
) -> None:
    """
    删除厂商API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        key_id: 密钥ID
        
    Raises:
        ProviderNotFoundError: 如果厂商不存在
        ProviderKeyServiceError: 如果密钥不存在或删除失败
    """
    # 检查厂商是否存在
    provider = session.get(Provider, provider_id)
    if not provider:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    
    # 获取密钥
    api_key = session.get(ProviderAPIKey, key_id)
    if not api_key or api_key.provider_id != provider_id:
        raise ProviderKeyServiceError(f"Provider key {key_id} not found for provider {provider_id}")
    
    session.delete(api_key)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ProviderKeyServiceError(f"Failed to delete provider key: {exc}") from exc
    
    logger.info(f"Deleted API key {key_id} for provider {provider_id}")


def get_provider_key_by_hash(
    session: Session,
    provider_id: str,
    key_hash: str,
) -> Optional[ProviderAPIKey]:
    """
    根据哈希值获取厂商API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        key_hash: 密钥哈希值
        
    Returns:
        厂商API密钥，如果不存在则返回None
    """
    stmt = select(ProviderAPIKey).where(
        ProviderAPIKey.provider_id == provider_id,
        ProviderAPIKey.key_hash == key_hash,
    )
    return session.execute(stmt).scalars().first()


def get_plaintext_key(api_key: ProviderAPIKey) -> str:
    """
    获取厂商API密钥的明文
    
    Args:
        api_key: 厂商API密钥对象
        
    Returns:
        明文密钥
        
    Raises:
        ProviderKeyServiceError: 如果解密失败
    """
    try:
        return decrypt_secret(api_key.encrypted_key)
    except Exception as exc:
        raise ProviderKeyServiceError(f"Failed to decrypt provider key: {exc}") from exc


def rotate_provider_key(
    session: Session,
    provider_id: str,
    key_id: str,
    new_key: str,
) -> ProviderAPIKey:
    """
    轮换厂商API密钥
    
    Args:
        session: 数据库会话
        provider_id: 厂商ID
        key_id: 密钥ID
        new_key: 新密钥
        
    Returns:
        更新后的厂商API密钥
        
    Raises:
        ProviderNotFoundError: 如果厂商不存在
        InvalidProviderKeyError: 如果新密钥无效
        ProviderKeyServiceError: 如果轮换失败
    """
    return update_provider_key(
        session,
        provider_id,
        key_id,
        ProviderAPIKeyUpdateRequest(key=new_key),
    )


__all__ = [
    "create_provider_key",
    "delete_provider_key",
    "DuplicateProviderKeyLabelError",
    "get_provider_key_by_hash",
    "get_provider_key_by_id",
    "get_plaintext_key",
    "InvalidProviderKeyError",
    "list_provider_keys",
    "ProviderKeyServiceError",
    "ProviderNotFoundError",
    "rotate_provider_key",
    "update_provider_key",
    "validate_provider_key",
]