"""
用户认证路由，处理用户登录、注册和令牌管理
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_refresh_token, require_jwt_token
from app.schemas.token import DeviceInfo
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.credit_service import get_or_create_account_for_user
from app.services.jwt_auth_service import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_access_token_with_jti,
    create_refresh_token,
    create_refresh_token_with_jti,
    extract_family_id_from_token,
    extract_jti_from_token,
    verify_password,
)
from app.services.token_redis_service import TokenRedisService
from app.services.role_service import RoleCodeAlreadyExistsError, RoleService
from app.services.user_permission_service import UserPermissionService
from app.services.user_service import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    create_user,
    get_user_by_id,
    update_user,
)
from app.services.registration_window_service import (
    RegistrationQuotaExceededError,
    RegistrationWindowClosedError,
    RegistrationWindowNotFoundError,
    claim_registration_slot,
    rollback_registration_slot,
)

router = APIRouter(tags=["authentication"], prefix="/auth")


DEFAULT_USER_ROLE_CODE = "default_user"


def _assign_default_role(db: Session, user_id: UUID) -> None:
    """为新注册用户分配默认角色。"""

    service = RoleService(db)
    role = service.get_role_by_code(DEFAULT_USER_ROLE_CODE)
    if role is None:
        try:
            role = service.create_role(
                code=DEFAULT_USER_ROLE_CODE,
                name="默认用户",
                description="系统默认普通用户角色",
            )
        except RoleCodeAlreadyExistsError:
            role = service.get_role_by_code(DEFAULT_USER_ROLE_CODE)
    if role is None:
        return

    service.set_user_roles(user_id, [role.id])


def _build_user_response(db: Session, user_id: UUID) -> UserResponse:
    """聚合用户基础信息 + 角色 + 能力标记列表，构造 UserResponse。"""

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    role_service = RoleService(db)
    perm_service = UserPermissionService(db)

    roles = role_service.get_user_roles(user.id)
    role_codes = [r.code for r in roles]
    can_create_private_provider = perm_service.has_permission(
        user.id, "create_private_provider"
    )
    can_submit_shared_provider = perm_service.has_permission(
        user.id, "submit_shared_provider"
    )
    permission_flags = [
        {
            "key": "can_create_private_provider",
            "value": bool(can_create_private_provider),
        },
        {
            "key": "can_submit_shared_provider",
            "value": bool(can_submit_shared_provider),
        },
    ]

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar=user.avatar,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_codes=role_codes,
        permission_flags=permission_flags,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


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
        window = claim_registration_slot(db)
    except RegistrationWindowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except (RegistrationWindowClosedError, RegistrationQuotaExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    try:
        # 将 RegisterRequest 映射到 UserCreateRequest 所需字段
        from app.schemas.user import UserCreateRequest

        # 生成基于邮箱的用户名
        username_prefix = request.email.split("@")[0]
        # 确保用户名唯一性
        from app.models import User
        from sqlalchemy import select
        existing_user = db.execute(select(User).where(User.username == username_prefix)).scalar_one_or_none()

        # 如果存在，添加数字后缀
        counter = 1
        username = username_prefix
        while existing_user is not None:
            username = f"{username_prefix}{counter}"
            existing_user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
            counter += 1

        payload = UserCreateRequest(
            username=username,
            email=request.email,
            password=request.password,
            display_name=request.display_name,
        )
        user = create_user(db, payload, is_active=window.auto_activate)
        # 为新注册用户创建默认积分账户（若未开启积分系统则仅做初始化，不影响行为）
        get_or_create_account_for_user(db, user.id)
        _assign_default_role(db, user.id)
        return _build_user_response(db, user.id)
    except UsernameAlreadyExistsError:
        rollback_registration_slot(db, window.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用",
        )
    except EmailAlreadyExistsError:
        rollback_registration_slot(db, window.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用",
        )
    except Exception:
        rollback_registration_slot(db, window.id)
        raise


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user_agent: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For"),
) -> TokenResponse:
    """
    用户登录并获取JWT令牌
    
    Args:
        request: 登录请求数据
        db: 数据库会话
        redis: Redis 连接
        user_agent: 用户代理字符串
        x_forwarded_for: 客户端 IP 地址
        
    Returns:
        JWT访问令牌和刷新令牌
        
    Raises:
        HTTPException: 如果用户名或密码错误
    """
    # 查找用户，只使用邮箱
    from sqlalchemy import select
    from app.models import User
    
    stmt = select(User).where(User.email == request.email)
    user = db.execute(stmt).scalars().first()
    
    # 如果用户不存在，返回通用错误信息
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱或密码错误",
        )
    
    # 验证密码
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱或密码错误",
        )
    
    # 检查用户是否处于活动状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )
    
    # 创建设备信息
    device_info = DeviceInfo(
        user_agent=user_agent,
        ip_address=x_forwarded_for.split(',')[0].strip() if x_forwarded_for else None
    )
    
    # 创建带 JTI 的 JWT 令牌
    access_token_data = {"sub": str(user.id)}
    refresh_token_data = {"sub": str(user.id)}
    
    access_token, access_jti, access_token_id = create_access_token_with_jti(access_token_data)
    refresh_token, refresh_jti, refresh_token_id, family_id = create_refresh_token_with_jti(
        refresh_token_data
    )
    
    # 存储 token 到 Redis
    token_service = TokenRedisService(redis)
    
    # 存储 access token
    await token_service.store_access_token(
        token_id=access_token_id,
        user_id=str(user.id),
        jti=access_jti,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        device_info=device_info,
    )
    
    # 存储 refresh token
    await token_service.store_refresh_token(
        token_id=refresh_token_id,
        user_id=str(user.id),
        jti=refresh_jti,
        family_id=family_id,
        expires_in=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        device_info=device_info,
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user_agent: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For"),
) -> TokenResponse:
    """
    使用刷新令牌获取新的访问令牌
    
    实现 token 轮换机制：
    - 验证旧的 refresh token
    - 检测 token 重用（安全防护）
    - 生成新的 token 对
    - 撤销旧的 refresh token
    
    Args:
        request: 刷新令牌请求
        db: 数据库会话
        redis: Redis 连接
        user_agent: 用户代理字符串
        x_forwarded_for: 客户端 IP 地址
        
    Returns:
        新的JWT访问令牌和刷新令牌
        
    Raises:
        HTTPException: 如果刷新令牌无效或检测到重用
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
        jti = payload.get("jti")
        family_id = payload.get("family_id")
        
        if not user_id or not jti or not family_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌载荷",
            )
        
        # 验证 Redis 中的 token 状态
        token_service = TokenRedisService(redis)
        token_record = await token_service.verify_refresh_token(jti)
        
        if not token_record:
            # Token 不存在或已被撤销，可能是重用攻击
            # 撤销整个 token 家族
            await token_service.revoke_token_family(
                family_id,
                reason="token_reuse_detected"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="检测到 token 重用，已撤销所有相关会话",
            )
        
        # 获取用户信息
        user = get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用",
            )
        
        # 创建设备信息
        device_info = DeviceInfo(
            user_agent=user_agent,
            ip_address=x_forwarded_for.split(',')[0].strip() if x_forwarded_for else None
        )
        
        # 生成新的令牌对（使用相同的 family_id）
        access_token_data = {"sub": str(user.id)}
        refresh_token_data = {"sub": str(user.id)}
        
        access_token, access_jti, access_token_id = create_access_token_with_jti(
            access_token_data
        )
        new_refresh_token, new_refresh_jti, new_refresh_token_id, _ = create_refresh_token_with_jti(
            refresh_token_data,
            family_id=family_id  # 保持相同的家族
        )
        
        # 撤销旧的 refresh token，添加 30 秒宽限期以允许飞行中的请求完成
        await token_service.revoke_token(jti, reason="token_rotated", grace_period_seconds=30)
        
        # 存储新的 access token
        await token_service.store_access_token(
            token_id=access_token_id,
            user_id=str(user.id),
            jti=access_jti,
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            device_info=device_info,
        )
        
        # 存储新的 refresh token（记录父 token）
        await token_service.store_refresh_token(
            token_id=new_refresh_token_id,
            user_id=str(user.id),
            jti=new_refresh_jti,
            family_id=family_id,
            expires_in=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            parent_jti=jti,  # 记录父 token
            device_info=device_info,
        )
        
        # 更新会话最后使用时间
        await token_service.update_session_last_used(user_id, new_refresh_jti)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的刷新令牌: {str(e)}",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    获取当前认证用户的信息
    
    Args:
        current_user: 当前认证用户
        
    Returns:
        用户信息
    """
    return _build_user_response(db, UUID(current_user.id))


@router.post("/logout")
async def logout(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    redis: Redis = Depends(get_redis),
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
) -> dict:
    """
    用户登出
    
    将当前 token 加入黑名单，使其立即失效
    
    Args:
        current_user: 当前认证用户
        redis: Redis 连接
        authorization: Authorization 头部
        x_auth_token: X-Auth-Token 头部
        
    Returns:
        登出结果
    """
    # 提取当前 token
    token = None
    if authorization:
        scheme, _, token_value = authorization.partition(" ")
        if scheme.lower() == "bearer" and token_value:
            token = token_value
    elif x_auth_token:
        token = x_auth_token.strip()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法获取当前 token"
        )
    
    # 提取 JTI
    jti = extract_jti_from_token(token)
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的 token"
        )
    
    # 撤销 token
    token_service = TokenRedisService(redis)
    success = await token_service.revoke_token(jti, reason="user_logout")
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token 撤销失败"
        )
    
    return {"message": "已成功登出"}


@router.post("/logout-all")
async def logout_all(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    redis: Redis = Depends(get_redis),
) -> dict:
    """
    登出所有设备
    
    撤销用户所有 token，使所有会话失效
    
    Args:
        current_user: 当前认证用户
        redis: Redis 连接
        
    Returns:
        登出结果
    """
    token_service = TokenRedisService(redis)
    count = await token_service.revoke_user_tokens(
        current_user.id,
        reason="user_logout_all"
    )
    
    return {
        "message": f"已成功登出所有设备",
        "revoked_sessions": count
    }


__all__ = ["router"]
