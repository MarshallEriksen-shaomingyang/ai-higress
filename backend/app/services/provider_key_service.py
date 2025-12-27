"""
厂商API密钥管理服务
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Provider, ProviderAPIKey
from app.repositories.provider_key_repository import (
    create_provider_key as repo_create_provider_key,
    delete_provider_key as repo_delete_provider_key,
    find_key_by_label as repo_find_key_by_label,
    get_provider_key_by_id as repo_get_provider_key_by_id,
    list_provider_keys as repo_list_provider_keys,
    list_provider_keys_plain as repo_list_provider_keys_plain,
    persist_provider_key as repo_persist_provider_key,
)
from app.repositories.provider_repository import get_provider_by_provider_id
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


def _get_provider_by_slug(session: Session, provider_id: str) -> Provider | None:
    """
    根据 provider 的短 ID（Provider.provider_id）查询 Provider 记录。

    路由层传入的是短 ID，例如 `openai` / `moonshot-xxx`，而数据库外键
    使用的是 Provider.id（UUID）。该辅助函数负责完成二者的映射。
    """
    return get_provider_by_provider_id(session, provider_id=provider_id)


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


def list_provider_keys(session: Session, provider_id: str) -> list[ProviderAPIKey]:
    """
    列出指定厂商的所有 API 密钥。

    路由层传入的是 provider 的短 ID（Provider.provider_id），这里需要先
    查出对应的 Provider，再通过 provider_uuid 外键过滤 ProviderAPIKey。
    """
    provider = _get_provider_by_slug(session, provider_id)
    if provider is None:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")

    return repo_list_provider_keys(session, provider_uuid=provider.id)


def get_provider_key_by_id(
    session: Session,
    provider_id: str,
    key_id: str
) -> ProviderAPIKey | None:
    """
    根据 ID 获取厂商 API 密钥。

    会同时校验该密钥是否属于指定 provider；如果不匹配则返回 None。
    """
    provider = _get_provider_by_slug(session, provider_id)
    if provider is None:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")

    api_key = repo_get_provider_key_by_id(session, key_id=key_id)
    if api_key is None or api_key.provider_uuid != provider.id:
        return None
    return api_key


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
    创建新的厂商 API 密钥。

    Args:
        session: 数据库会话
        provider_id: Provider 的短 ID（provider.provider_id）
        payload: 创建请求
    """
    provider = _get_provider_by_slug(session, provider_id)
    if provider is None:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")

    # 验证密钥
    if not validate_provider_key(provider_id, payload.key):
        raise InvalidProviderKeyError(f"Invalid API key for provider {provider_id}")

    # 检查标签是否已存在（同一 Provider 下 label 需唯一）
    existing = repo_find_key_by_label(
        session,
        provider_uuid=provider.id,
        label=payload.label,
    )
    if existing:
        raise DuplicateProviderKeyLabelError(
            f"Label '{payload.label}' already exists for provider {provider_id}"
        )

    # 加密并创建密钥
    encrypted_key = encrypt_secret(payload.key)

    api_key = ProviderAPIKey(
        provider_uuid=provider.id,
        encrypted_key=encrypted_key,
        label=payload.label,
        weight=payload.weight,
        max_qps=payload.max_qps,
        status=payload.status,
    )

    try:
        api_key = repo_create_provider_key(session, api_key=api_key)
    except IntegrityError as exc:
        raise ProviderKeyServiceError(f"Failed to create provider key: {exc}") from exc
    logger.info(
        "Created new API key for provider %s (label=%s, id=%s)",
        provider_id,
        payload.label,
        api_key.id,
    )
    return api_key


def update_provider_key(
    session: Session,
    provider_id: str,
    key_id: str,
    payload: ProviderAPIKeyUpdateRequest,
    ) -> ProviderAPIKey:
    """
    更新厂商 API 密钥。

    Args:
        session: 数据库会话
        provider_id: Provider 的短 ID（provider.provider_id）
        key_id: 密钥 ID
        payload: 更新请求
    """
    provider = _get_provider_by_slug(session, provider_id)
    if provider is None:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")

    api_key = repo_get_provider_key_by_id(session, key_id=key_id)
    if api_key is None or api_key.provider_uuid != provider.id:
        raise ProviderKeyServiceError(
            f"Provider key {key_id} not found for provider {provider_id}"
        )

    # 如果提供了新密钥，则验证并更新
    if payload.key:
        if not validate_provider_key(provider_id, payload.key):
            raise InvalidProviderKeyError(
                f"Invalid API key for provider {provider_id}"
            )
        api_key.encrypted_key = encrypt_secret(payload.key)

    # 检查标签是否与其他密钥冲突
    if payload.label and payload.label != api_key.label:
        existing = repo_find_key_by_label(
            session,
            provider_uuid=provider.id,
            label=payload.label,
            exclude_key_id=key_id,
        )
        if existing:
            raise DuplicateProviderKeyLabelError(
                f"Label '{payload.label}' already exists for provider {provider_id}"
            )
        api_key.label = payload.label

    # 更新其他字段
    if payload.weight is not None:
        api_key.weight = payload.weight

    if payload.max_qps is not None:
        api_key.max_qps = payload.max_qps

    if payload.status is not None:
        api_key.status = payload.status

    try:
        api_key = repo_persist_provider_key(session, api_key=api_key)
    except IntegrityError as exc:
        raise ProviderKeyServiceError(f"Failed to update provider key: {exc}") from exc
    logger.info("Updated API key %s for provider %s", key_id, provider_id)
    return api_key


def delete_provider_key(
    session: Session,
    provider_id: str,
    key_id: str,
) -> None:
    """
    删除厂商 API 密钥。

    Args:
        session: 数据库会话
        provider_id: Provider 的短 ID（provider.provider_id）
        key_id: 密钥 ID
    """
    provider = _get_provider_by_slug(session, provider_id)
    if provider is None:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")

    api_key = repo_get_provider_key_by_id(session, key_id=key_id)
    if api_key is None or api_key.provider_uuid != provider.id:
        raise ProviderKeyServiceError(
            f"Provider key {key_id} not found for provider {provider_id}"
        )

    try:
        repo_delete_provider_key(session, api_key=api_key)
    except IntegrityError as exc:
        raise ProviderKeyServiceError(f"Failed to delete provider key: {exc}") from exc

    logger.info("Deleted API key %s for provider %s", key_id, provider_id)


def get_provider_key_by_hash(
    session: Session,
    provider_id: str,
    key_hash: str,
) -> ProviderAPIKey | None:
    """
    根据哈希值获取厂商 API 密钥。

    由于数据库模型当前未单独存储 key_hash，这里通过解密所有该 Provider 的
    密钥并在内存中比对哈希值。该函数目前仅在内部使用，调用频率有限。
    """
    provider = _get_provider_by_slug(session, provider_id)
    if provider is None:
        return None

    for api_key in repo_list_provider_keys_plain(session, provider_uuid=provider.id):
        try:
            plaintext = decrypt_secret(api_key.encrypted_key)
        except Exception:
            # 解密失败的 key 直接跳过，不影响其他 key 的查找。
            continue
        if _hash_provider_key(provider_id, plaintext) == key_hash:
            return api_key
    return None


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
    "DuplicateProviderKeyLabelError",
    "InvalidProviderKeyError",
    "ProviderKeyServiceError",
    "ProviderNotFoundError",
    "create_provider_key",
    "delete_provider_key",
    "get_plaintext_key",
    "get_provider_key_by_hash",
    "get_provider_key_by_id",
    "list_provider_keys",
    "rotate_provider_key",
    "update_provider_key",
    "validate_provider_key",
]
