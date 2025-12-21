"""
统一的密钥管理服务，替代脚本生成密钥的方式
"""

import secrets

from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import User
from app.schemas.api_key import APIKeyCreateRequest, APIKeyExpiry
from app.schemas.user import UserCreateRequest
from app.services.api_key_service import create_api_key
from app.services.user_service import create_user
from app.settings import settings


class KeyManagementServiceError(Exception):
    """密钥管理服务基础错误"""
    pass


class SystemKeyGenerationError(KeyManagementServiceError):
    """系统密钥生成错误"""
    pass


class UserCreationError(KeyManagementServiceError):
    """用户创建错误"""
    pass


class APIKeyGenerationError(KeyManagementServiceError):
    """API密钥生成错误"""
    pass


def generate_system_secret_key(length: int = 64) -> str:
    """
    生成系统主密钥
    
    Args:
        length: 密钥长度
        
    Returns:
        随机生成的系统密钥
        
    Raises:
        SystemKeyGenerationError: 如果生成失败
    """
    try:
        # 生成足够强度的随机密钥
        secret_key = secrets.token_urlsafe(length)
        logger.info("Generated new system secret key")
        return secret_key
    except Exception as exc:
        raise SystemKeyGenerationError(f"Failed to generate system secret key: {exc}") from exc


def generate_secure_random_password(length: int = 16) -> str:
    """
    生成安全的随机密码
    
    Args:
        length: 密码长度（字符数，默认16）
        
    Returns:
        随机生成的密码（保证不超过72字节）
        
    Raises:
        SystemKeyGenerationError: 如果生成失败
    """
    try:
        # 生成安全的随机密码，确保不超过 72 字节（bcrypt 限制）
        # secrets.token_urlsafe(n) 生成大约 4*n/3 长度的 base64 字符串
        # 为了确保不超过 72 字节，我们使用较小的值
        # token_urlsafe(32) 生成约 43 字符，远小于 72 字节
        actual_length = min(length, 32)
        password = secrets.token_urlsafe(actual_length)
        # 双重保险：确保不超过 72 字节
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password = password_bytes[:72].decode('utf-8', errors='ignore')
        return password
    except Exception as exc:
        raise SystemKeyGenerationError(f"Failed to generate secure password: {exc}") from exc


def create_user_with_api_key(
    session: Session,
    username: str,
    email: str,
    display_name: str = None,
    password: str = None,
    is_superuser: bool = False,
    api_key_name: str = None,
    api_key_expiry: APIKeyExpiry = APIKeyExpiry.NEVER,
) -> tuple[User, str, str]:
    """
    创建用户并生成API密钥
    
    Args:
        session: 数据库会话
        username: 用户名
        email: 邮箱
        display_name: 显示名称
        password: 密码，如果不提供则自动生成
        is_superuser: 是否为超级用户
        api_key_name: API密钥名称
        api_key_expiry: API密钥过期时间
        
    Returns:
        (用户对象, 明文密码, API密钥令牌)
        
    Raises:
        UserCreationError: 如果用户创建失败
        APIKeyGenerationError: 如果API密钥生成失败
    """
    try:
        # 如果未提供密码，则生成一个
        if not password:
            password = generate_secure_random_password()

        # 创建用户
        user_payload = UserCreateRequest(
            username=username,
            email=email,
            password=password,
            display_name=display_name or username,
        )

        # 打印密码长度以调试
        if password and len(password.encode('utf-8')) > 72:
            print(f"Password too long: {len(password.encode('utf-8'))} bytes, truncating")

        user = create_user(session, user_payload, is_superuser=is_superuser)

        # 生成API密钥
        if not api_key_name:
            api_key_name = f"{username}-default-key"

        api_key_payload = APIKeyCreateRequest(
            name=api_key_name,
            expiry=api_key_expiry,
        )

        api_key, api_token = create_api_key(session, user=user, payload=api_key_payload)

        logger.info(f"Created user {username} with API key {api_key_name}")
        return user, password, api_token

    except Exception as exc:
        # 根据异常类型抛出相应的错误
        if "username" in str(exc).lower() or "email" in str(exc).lower():
            raise UserCreationError(f"Failed to create user: {exc}") from exc
        else:
            raise APIKeyGenerationError(f"Failed to create API key: {exc}") from exc


def initialize_system_admin(
    session: Session,
    username: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
) -> dict[str, str]:
    """
    初始化系统管理员账户
    
    Args:
        session: 数据库会话
        username: 管理员用户名
        email: 管理员邮箱
        display_name: 管理员显示名称
        
    Returns:
        包含管理员凭证的字典
        
    Raises:
        KeyManagementServiceError: 如果初始化失败
    """
    try:
        username = username or settings.default_admin_username
        email = email or settings.default_admin_email
        display_name = display_name or "System Administrator"

        # 检查是否已有管理员
        from app.services.user_service import has_any_user
        if has_any_user(session):
            raise KeyManagementServiceError("System already has users")

        password = generate_secure_random_password()
        user_payload = UserCreateRequest(
            username=username,
            email=email,
            password=password,
            display_name=display_name,
        )
        try:
            user = create_user(session, user_payload, is_superuser=True)
        except Exception as exc:
            raise UserCreationError(f"Failed to create user: {exc}") from exc

        result = {
            "user": user,
            "username": user.username,
            "email": user.email,
            "password": password,
        }

        logger.warning(
            "System admin initialized - please save credentials securely: username=%s email=%s",
            username,
            email,
        )

        return result

    except KeyManagementServiceError:
        raise
    except Exception as exc:
        raise KeyManagementServiceError(f"Failed to initialize system admin: {exc}") from exc


def rotate_system_secret_key() -> str:
    """
    轮换系统主密钥
    
    Warning: 轮换系统密钥会使所有现有的密码哈希和API密钥失效！
    这需要重新哈希所有密码和重新生成所有API密钥。
    
    Returns:
        新生成的系统密钥
        
    Raises:
        SystemKeyGenerationError: 如果轮换失败
    """
    # 注意：在实际实现中，这里应该包含重新哈希所有密码和重新生成所有API密钥的逻辑
    # 这是一个非常危险的操作，应该谨慎实现

    new_key = generate_system_secret_key()
    logger.warning("System secret key rotation initiated - all passwords and API keys will need to be reset")

    # TODO: 实现完整的密钥轮换逻辑

    return new_key


def validate_key_strength(key: str) -> bool:
    """
    验证密钥强度
    
    Args:
        key: 要验证的密钥
        
    Returns:
        密钥是否足够强
    """
    if len(key) < 32:
        return False

    # 检查密钥是否包含足够的熵
    # 这是一个简单的检查，实际应用中可能需要更复杂的逻辑
    entropy_chars = set(key)
    if len(entropy_chars) < 20:
        return False

    return True


__all__ = [
    "APIKeyGenerationError",
    "KeyManagementServiceError",
    "SystemKeyGenerationError",
    "UserCreationError",
    "create_user_with_api_key",
    "generate_secure_random_password",
    "generate_system_secret_key",
    "initialize_system_admin",
    "rotate_system_secret_key",
    "validate_key_strength",
]
