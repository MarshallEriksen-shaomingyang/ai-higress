"""
用户认证路由，处理用户登录、注册和令牌管理
"""

from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_http_client, get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_refresh_token, require_jwt_token
from app.models import User
from app.settings import settings
from app.schemas.token import DeviceInfo
from app.schemas.auth import (
    LoginRequest,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserCreateRequest, UserResponse
from app.services.avatar_service import build_avatar_url
from app.services.jwt_auth_service import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token_with_jti,
    create_refresh_token_with_jti,
    extract_family_id_from_token,
    extract_jti_from_token,
    verify_password,
)
from app.services.linuxdo_oauth_service import (
    LinuxDoOAuthError,
    build_linuxdo_authorize_url,
    complete_linuxdo_oauth_flow,
)
from app.services.token_redis_service import TokenRedisService
from app.services.role_service import RoleService
from app.services.user_permission_service import UserPermissionService
from app.services.user_service import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    get_user_by_id,
    register_user_with_window,
)
from app.services.registration_window_service import (
    RegistrationQuotaExceededError,
    RegistrationWindowClosedError,
    RegistrationWindowNotFoundError,
)

router = APIRouter(tags=["authentication"], prefix="/auth")


def _request_base_url(request: Request | None) -> str | None:
    """提取请求基址（去掉末尾斜杠），用于拼接头像 URL。"""

    if request is None:
        return None
    return str(request.base_url).rstrip("/")


def _build_user_response(
    db: Session,
    user_id: UUID,
    *,
    requires_manual_activation: bool = False,
    request_base_url: str | None = None,
) -> UserResponse:
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
        avatar=build_avatar_url(
            user.avatar,
            request_base_url=request_base_url,
        ),
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        requires_manual_activation=requires_manual_activation,
        role_codes=role_codes,
        permission_flags=permission_flags,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _build_device_info(
    user_agent: Optional[str],
    x_forwarded_for: Optional[str],
) -> DeviceInfo:
    ip_address = None
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(",")[0].strip()
    return DeviceInfo(
        user_agent=user_agent,
        ip_address=ip_address or None,
    )


async def _issue_token_pair(
    user: User,
    redis: Redis,
    device_info: DeviceInfo,
) -> TokenResponse:
    access_token_data = {"sub": str(user.id)}
    refresh_token_data = {"sub": str(user.id)}

    access_token, access_jti, access_token_id = create_access_token_with_jti(
        access_token_data
    )
    refresh_token, refresh_jti, refresh_token_id, family_id = create_refresh_token_with_jti(
        refresh_token_data
    )

    token_service = TokenRedisService(redis)
    await token_service.store_access_token(
        token_id=access_token_id,
        user_id=str(user.id),
        jti=access_jti,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        device_info=device_info,
    )
    await token_service.store_refresh_token(
        token_id=refresh_token_id,
        user_id=str(user.id),
        jti=refresh_jti,
        family_id=family_id,
        expires_in=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        device_info=device_info,
    )
    await token_service.enforce_session_limit(
        str(user.id),
        settings.max_sessions_per_user,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    http_request: Request,
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
        payload = UserCreateRequest(
            username=None,
            email=request.email,
            password=request.password,
            display_name=request.display_name,
        )
        user, requires_manual_activation = register_user_with_window(db, payload)
        return _build_user_response(
            db,
            user.id,
            requires_manual_activation=requires_manual_activation,
            request_base_url=_request_base_url(http_request),
        )
    except RegistrationWindowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except (RegistrationWindowClosedError, RegistrationQuotaExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except UsernameAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用",
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
    redis: Redis = Depends(get_redis),
    user_agent: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For"),
) -> TokenResponse:
    """
    用户登录并获取JWT令牌
    """
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
    
    device_info = _build_device_info(user_agent, x_forwarded_for)
    return await _issue_token_pair(user, redis, device_info)


@router.get("/oauth/linuxdo/authorize", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def linuxdo_oauth_authorize(
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """
    生成 LinuxDo 授权链接并重定向。
    """

    try:
        authorize_url = await build_linuxdo_authorize_url(redis)
    except LinuxDoOAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return RedirectResponse(
        authorize_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.post("/oauth/callback", response_model=OAuthCallbackResponse)
async def linuxdo_oauth_callback(
    payload: OAuthCallbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client: httpx.AsyncClient = Depends(get_http_client),
    user_agent: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For"),
) -> OAuthCallbackResponse:
    """
    处理 LinuxDo OAuth 回调，完成用户同步与登录。
    """

    try:
        user, requires_manual_activation = await complete_linuxdo_oauth_flow(
            db,
            redis,
            client,
            code=payload.code,
            state=payload.state,
        )
    except LinuxDoOAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    if requires_manual_activation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已创建，等待管理员激活",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    device_info = _build_device_info(user_agent, x_forwarded_for)
    token_pair = await _issue_token_pair(user, redis, device_info)
    user_response = _build_user_response(
        db,
        user.id,
        request_base_url=_request_base_url(request),
    )

    return OAuthCallbackResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
        token_type=token_pair.token_type,
        user=user_response,
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

        # 刷新令牌成功后，同样执行会话数量限制，避免短时间内刷出过多会话
        await token_service.enforce_session_limit(
            str(user.id),
            settings.max_sessions_per_user,
        )
        
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
    request: Request,
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
    return _build_user_response(
        db,
        UUID(current_user.id),
        request_base_url=_request_base_url(request),
    )


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
