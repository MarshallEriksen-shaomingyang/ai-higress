"""
用户认证路由，处理用户登录、注册和令牌管理
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.jwt_auth import AuthenticatedUser, require_jwt_refresh_token, require_jwt_token
from app.schemas.user import UserResponse
from app.services.jwt_auth_service import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.services.user_service import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    create_user,
    get_user_by_id,
    update_user,
)

router = APIRouter(tags=["authentication"], prefix="/auth")


# 请求和响应模型
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 访问令牌过期时间（秒）


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    password: str = Field(..., min_length=6)
    display_name: str = None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    用户注册
    
    Args:
        request: 注册请求数据
        db: 数据库会话
        
    Returns:
        用户信息
        
    Raises:
        HTTPException: 如果用户名或邮箱已存在
    """
    try:
        user = create_user(
            db,
            {
                "username": request.username,
                "email": request.email,
                "password": request.password,
                "display_name": request.display_name,
            },
        )
        return UserResponse.model_validate(user)
    except UsernameAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    用户登录并获取JWT令牌
    
    Args:
        request: 登录请求数据
        db: 数据库会话
        
    Returns:
        JWT访问令牌和刷新令牌
        
    Raises:
        HTTPException: 如果用户名或密码错误
    """
    # 查找用户
    user = None
    # 尝试按用户名查找
    from sqlalchemy import select
    from app.models import User
    
    stmt = select(User).where(User.username == request.username)
    user = db.execute(stmt).scalars().first()
    
    # 如果按用户名找不到，尝试按邮箱查找
    if user is None:
        stmt = select(User).where(User.email == request.username)
        user = db.execute(stmt).scalars().first()
    
    # 如果用户不存在，返回通用错误信息
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证密码
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户是否处于活动状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )
    
    # 创建JWT令牌
    access_token_data = {"sub": str(user.id)}
    refresh_token_data = {"sub": str(user.id)}
    
    access_token = create_access_token(access_token_data)
    refresh_token = create_refresh_token(refresh_token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    使用刷新令牌获取新的访问令牌
    
    Args:
        request: 刷新令牌请求
        db: 数据库会话
        
    Returns:
        新的JWT访问令牌和刷新令牌
        
    Raises:
        HTTPException: 如果刷新令牌无效
    """
    try:
        # 验证刷新令牌
        from app.services.jwt_auth_service import decode_token
        payload = decode_token(request.refresh_token)
        
        # 检查令牌类型
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌类型",
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌载荷",
            )
        
        # 获取用户信息
        user = get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用",
            )
        
        # 生成新的令牌
        access_token_data = {"sub": str(user.id)}
        refresh_token_data = {"sub": str(user.id)}
        
        access_token = create_access_token(access_token_data)
        refresh_token = create_refresh_token(refresh_token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """
    获取当前认证用户的信息
    
    Args:
        current_user: 当前认证用户
        
    Returns:
        用户信息
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar=current_user.avatar,
        is_superuser=current_user.is_superuser,
    )


@router.post("/logout")
async def logout(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict:
    """
    用户登出
    
    注意：由于JWT是无状态的，实际的登出需要在客户端删除令牌。
    这个端点主要用于记录登出事件或实现令牌黑名单。
    
    Args:
        current_user: 当前认证用户
        
    Returns:
        登出结果
    """
    # TODO: 实现令牌黑名单或记录登出事件
    return {"message": "已成功登出"}


__all__ = ["router"]