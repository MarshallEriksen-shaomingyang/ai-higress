"""
JWT认证服务，用于用户登录令牌的管理和验证
"""

import datetime
import uuid
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.settings import settings

# JWT配置
JWT_SECRET_KEY = settings.secret_key
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 访问令牌有效期30分钟
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7    # 刷新令牌有效期7天


def hash_password(password: str) -> str:
    """
    使用bcrypt哈希密码
    
    Args:
        password: 原始密码
        
    Returns:
        哈希后的密码
    """
    # 确保密码不超过 72 字节（bcrypt 限制）
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # 按字节截断
        password_bytes = password_bytes[:72]

    # 直接使用 bcrypt 库，避免 passlib 的初始化问题
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 原始密码
        hashed_password: 哈希后的密码
        
    Returns:
        验证是否通过
    """
    # 确保密码不超过 72 字节
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    # 直接使用 bcrypt 库
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict[str, Any], expires_delta: datetime.timedelta | None = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码到令牌中的数据
        expires_delta: 自定义过期时间
        
    Returns:
        JWT访问令牌
    """
    to_encode = data.copy()

    # 使用带时区的 UTC 时间，避免 datetime.utcnow() 的弃用警告
    now = datetime.datetime.now(datetime.UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    创建刷新令牌
    
    Args:
        data: 要编码到令牌中的数据
        
    Returns:
        JWT刷新令牌
    """
    to_encode = data.copy()
    # 使用带时区的 UTC 时间
    now = datetime.datetime.now(datetime.UTC)
    expire = now + datetime.timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    解码JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        解码后的令牌数据
        
    Raises:
        JWTError: 如果令牌无效
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise


def verify_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """
    验证JWT令牌
    
    Args:
        token: JWT令牌
        token_type: 令牌类型 ("access" 或 "refresh")
        
    Returns:
        令牌数据
        
    Raises:
        JWTError: 如果令牌无效或类型不匹配
    """
    payload = decode_token(token)

    # 检查令牌类型
    if payload.get("type") != token_type:
        raise JWTError(f"Invalid token type: expected {token_type}")

    # 检查过期时间（由jwt.decode自动处理）
    return payload


def create_access_token_with_jti(
    data: dict[str, Any], expires_delta: datetime.timedelta | None = None
) -> tuple[str, str, str]:
    """
    创建带 JTI 的 access token
    
    Args:
        data: 要编码到令牌中的数据
        expires_delta: 自定义过期时间
        
    Returns:
        (token, jti, token_id) 元组
    """
    to_encode = data.copy()
    token_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())

    # 使用带时区的 UTC 时间
    now = datetime.datetime.now(datetime.UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access", "jti": jti, "token_id": token_id})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt, jti, token_id


def create_refresh_token_with_jti(
    data: dict[str, Any], family_id: str | None = None
) -> tuple[str, str, str, str]:
    """
    创建带 JTI 的 refresh token
    
    Args:
        data: 要编码到令牌中的数据
        family_id: Token 家族 ID（用于轮换追踪）
        
    Returns:
        (token, jti, token_id, family_id) 元组
    """
    to_encode = data.copy()
    token_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())

    if family_id is None:
        family_id = str(uuid.uuid4())

    # 使用带时区的 UTC 时间
    now = datetime.datetime.now(datetime.UTC)
    expire = now + datetime.timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": jti,
        "token_id": token_id,
        "family_id": family_id
    })
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt, jti, token_id, family_id


def extract_jti_from_token(token: str) -> str | None:
    """
    从 token 中提取 JTI
    
    Args:
        token: JWT 令牌
        
    Returns:
        JTI 或 None
    """
    try:
        payload = decode_token(token)
        return payload.get("jti")
    except JWTError:
        return None


def extract_token_id_from_token(token: str) -> str | None:
    """
    从 token 中提取 token_id
    
    Args:
        token: JWT 令牌
        
    Returns:
        token_id 或 None
    """
    try:
        payload = decode_token(token)
        return payload.get("token_id")
    except JWTError:
        return None


def extract_family_id_from_token(token: str) -> str | None:
    """
    从 refresh token 中提取 family_id
    
    Args:
        token: JWT 刷新令牌
        
    Returns:
        family_id 或 None
    """
    try:
        payload = decode_token(token)
        return payload.get("family_id")
    except JWTError:
        return None


__all__ = [
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    "create_access_token",
    "create_access_token_with_jti",
    "create_refresh_token",
    "create_refresh_token_with_jti",
    "decode_token",
    "extract_family_id_from_token",
    "extract_jti_from_token",
    "extract_token_id_from_token",
    "hash_password",
    "verify_password",
    "verify_token",
]
