"""
JWT认证服务，用于用户登录令牌的管理和验证
"""

import datetime
from typing import Any, Dict, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.settings import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 原始密码
        hashed_password: 哈希后的密码
        
    Returns:
        验证是否通过
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码到令牌中的数据
        expires_delta: 自定义过期时间
        
    Returns:
        JWT访问令牌
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    创建刷新令牌
    
    Args:
        data: 要编码到令牌中的数据
        
    Returns:
        JWT刷新令牌
    """
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
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


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
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


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
]