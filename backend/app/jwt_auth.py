"""
JWT认证中间件和依赖，用于处理用户登录令牌
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.services.avatar_service import build_avatar_url
from app.services.jwt_auth_service import verify_token
from app.services.token_redis_service import TokenRedisService
from app.services.user_service import get_user_by_id
from app.settings import settings


@dataclass
class AuthenticatedUser:
    """已认证的用户信息"""
    id: str
    username: str
    email: str
    is_superuser: bool
    is_active: bool
    display_name: str | None = None
    avatar: str | None = None


def _get_token_from_headers(
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None, alias="X-Auth-Token"),
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
    token_value: str | None = None

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
    request: Request,
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None, alias="X-Auth-Token"),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthenticatedUser:
    """
    验证JWT访问令牌并返回已认证的用户
    
    增强的验证流程：
    1. 验证 JWT 签名和过期时间
    2. 检查 Redis 中的 token 状态
    3. 检查黑名单
    4. 验证用户状态
    
    Args:
        authorization: Authorization头部值
        x_auth_token: X-Auth-Token头部值
        db: 数据库会话
        redis: Redis 连接
        
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
    jti: str | None = payload.get("jti")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # 如果 token 带有 JTI，则按“有状态模式”在 Redis 中进一步校验。
    #
    # 注意：生产环境必须要求 token 包含 JTI，以确保撤销/黑名单/会话控制有效。
    # 非生产环境允许缺省 JTI，主要用于测试与兼容旧 token（仅验签名+过期时间）。
    if not jti:
        if settings.environment.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        token_service = TokenRedisService(redis)
        # 检查黑名单
        if await token_service.is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 验证 token 记录
        token_record = await token_service.verify_access_token(jti)
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 验证用户
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
    request_base_url = str(request.base_url).rstrip("/")

    return AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        display_name=user.display_name,
        avatar=build_avatar_url(
            user.avatar,
            request_base_url=request_base_url,
        ),
    )


async def require_jwt_refresh_token(
    request: Request,
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None, alias="X-Auth-Token"),
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
    request_base_url = str(request.base_url).rstrip("/")

    return AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        display_name=user.display_name,
        avatar=build_avatar_url(
            user.avatar,
            request_base_url=request_base_url,
        ),
    )


__all__ = [
    "AuthenticatedUser",
    "require_jwt_refresh_token",
    "require_jwt_token",
]
