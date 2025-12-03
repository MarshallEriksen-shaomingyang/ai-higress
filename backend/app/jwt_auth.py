"""
JWT认证中间件和依赖，用于处理用户登录令牌
"""

import datetime
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.services.jwt_auth_service import verify_token
from app.services.user_service import get_user_by_id


@dataclass
class AuthenticatedUser:
    """已认证的用户信息"""
    id: str
    username: str
    email: str
    is_superuser: bool
    is_active: bool
    display_name: Optional[str] = None
    avatar: Optional[str] = None


def _get_token_from_headers(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
) -> str:
    """
    从HTTP头部提取JWT令牌
    
    Args:
        authorization: Authorization头部值
        x_auth_token: X-Auth-Token头部值
        
    Returns:
        JWT令牌字符串
        
    Raises:
        HTTPException: 如果令牌缺失或格式错误
    """
    token_value: Optional[str] = None
    
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header, expected 'Bearer <token>'",
            )
        token_value = token
    elif x_auth_token:
        token_value = x_auth_token.strip()
    
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization or X-Auth-Token header",
        )
    
    return token_value


async def require_jwt_token(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """
    验证JWT访问令牌并返回已认证的用户
    
    Args:
        authorization: Authorization头部值
        x_auth_token: X-Auth-Token头部值
        db: 数据库会话
        
    Returns:
        已认证的用户信息
        
    Raises:
        HTTPException: 如果令牌无效或用户不存在
    """
    token = _get_token_from_headers(authorization, x_auth_token)
    
    try:
        payload = verify_token(token, token_type="access")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        display_name=user.display_name,
        avatar=user.avatar,
    )


async def require_jwt_refresh_token(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """
    验证JWT刷新令牌并返回已认证的用户
    
    Args:
        authorization: Authorization头部值
        x_auth_token: X-Auth-Token头部值
        db: 数据库会话
        
    Returns:
        已认证的用户信息
        
    Raises:
        HTTPException: 如果令牌无效或用户不存在
    """
    token = _get_token_from_headers(authorization, x_auth_token)
    
    try:
        payload = verify_token(token, token_type="refresh")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        display_name=user.display_name,
        avatar=user.avatar,
    )


__all__ = [
    "AuthenticatedUser",
    "require_jwt_token",
    "require_jwt_refresh_token",
]