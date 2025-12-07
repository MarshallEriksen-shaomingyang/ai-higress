"""
用户管理路由 - V2版本，使用JWT认证
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_redis
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.services.api_key_cache import invalidate_cached_api_key
from app.services.role_service import RoleCodeAlreadyExistsError, RoleService
from app.services.user_permission_service import UserPermissionService
from app.services.avatar_service import build_avatar_url, get_avatar_file_path
from app.services.user_service import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    create_user,
    get_user_by_id,
    set_user_active,
    update_user,
)
from app.services.credit_service import get_or_create_account_for_user
from app.services.token_redis_service import TokenRedisService

router = APIRouter(
    tags=["users"],
    dependencies=[Depends(require_jwt_token)],
)


DEFAULT_USER_ROLE_CODE = "default_user"


def _assign_default_role(db: Session, user_id: UUID) -> None:
    """为新用户分配默认角色（若不存在则自动创建）。"""

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
            # 并发场景下如果已经被其他进程创建，则重新查询
            role = service.get_role_by_code(DEFAULT_USER_ROLE_CODE)
    if role is None:
        return

    # 对于新用户，直接设置为该默认角色即可
    service.set_user_roles(user_id, [role.id])


def _build_user_response(db: Session, user_id: UUID) -> UserResponse:
    """聚合用户基础信息 + 角色 + 能力标记列表，构造 UserResponse。"""

    user = get_user_by_id(db, user_id)
    if user is None:
        raise not_found(f"User {user_id} not found")

    role_service = RoleService(db)
    perm_service = UserPermissionService(db)

    roles = role_service.get_user_roles(user.id)
    role_codes = [r.code for r in roles]
    # 只暴露关键能力布尔值，通过列表封装，细粒度权限仍由后端校验
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
        avatar=build_avatar_url(user.avatar),
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_codes=role_codes,
        permission_flags=permission_flags,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user_endpoint(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """注册一个新用户并存储哈希密码。"""

    try:
        user = create_user(db, payload)
    except UsernameAlreadyExistsError:
        raise bad_request("用户名已存在")
    except EmailAlreadyExistsError:
        raise bad_request("邮箱已被使用")

    # 为新用户分配默认角色
    _assign_default_role(db, user.id)
    # 初始化积分账户（如已存在则直接返回）
    get_or_create_account_for_user(db, user.id)

    return _build_user_response(db, user.id)


@router.get("/users/me", response_model=UserResponse)
def get_current_user_endpoint(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """获取当前认证用户的信息。"""
    return _build_user_response(db, UUID(current_user.id))


@router.post("/users/me/avatar", response_model=UserResponse)
async def upload_my_avatar_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """
    上传并更新当前用户的头像。

    实现约定：
    - 当前阶段文件实际保存到本地目录 AVATAR_LOCAL_DIR（默认 backend/media/avatars）；
    - 数据库 users.avatar 字段仅保存相对 key，例如 "<user_id>/<uuid>.png"；
    - 对外返回的 UserResponse.avatar 始终是可直接访问的 URL：
      - 若配置了 AVATAR_OSS_BASE_URL，则为 "<AVATAR_OSS_BASE_URL>/<key>"；
      - 否则为 "<AVATAR_LOCAL_BASE_URL>/<key>"（默认 /media/avatars/<key>）。
    """

    # 只允许常见图片格式，避免用户误上传其他文件
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    if file.content_type not in allowed_types:
        raise bad_request("不支持的头像图片类型，请上传 PNG/JPEG/WebP 格式")

    # 从文件名推断后缀
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in {"png", "jpg", "jpeg", "webp"}:
            # 统一转为 .png 以避免奇怪后缀
            ext = "png"
    else:
        ext = "png"

    user = get_user_by_id(db, UUID(current_user.id))
    if user is None:
        raise not_found(f"User {current_user.id} not found")

    # 为当前用户生成新的头像 key，形如 "<user_id>/<random>.png"
    avatar_key = f"{user.id}/{uuid4().hex}.{ext}"
    avatar_path = get_avatar_file_path(avatar_key)
    avatar_path.parent.mkdir(parents=True, exist_ok=True)

    # 简单限制单个头像文件大小：2MB
    max_bytes = 2 * 1024 * 1024
    written = 0

    try:
        with avatar_path.open("wb") as out:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    # 删除已写入的临时文件，避免残留无效大文件
                    out.close()
                    avatar_path.unlink(missing_ok=True)
                    raise bad_request("头像文件过大，最大支持 2MB")
                out.write(chunk)
    finally:
        # 无论如何都关闭上传文件，避免后续误用
        await file.close()

    # 更新用户记录，仅保存 key，URL 在响应构造时再拼接
    user.avatar = avatar_key
    db.add(user)
    db.commit()
    db.refresh(user)

    return _build_user_response(db, user.id)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """更新可编辑的用户资料字段和密码。"""
    
    # 检查权限：用户只能更新自己的信息，除非是超级用户
    if not current_user.is_superuser and current_user.id != str(user_id):
        raise forbidden("无权修改其他用户信息")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise not_found(f"User {user_id} not found")

    try:
        updated = update_user(db, user, payload)
    except EmailAlreadyExistsError:
        raise bad_request("邮箱已被使用")
    return _build_user_response(db, updated.id)


async def _invalidate_user_api_keys(redis, key_hashes: list[str]) -> None:
    for key_hash in key_hashes:
        await invalidate_cached_api_key(redis, key_hash)


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status_endpoint(
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserResponse:
    """允许超级用户禁用/恢复用户，禁用时立即撤销其 API 密钥缓存及所有 JWT 会话。"""

    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以封禁用户")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise not_found(f"User {user_id} not found")

    updated, key_hashes = set_user_active(db, user, is_active=payload.is_active)

    # 无论启用还是禁用，都清理已有的 API Key 缓存，避免状态漂移
    await _invalidate_user_api_keys(redis, key_hashes)

    # 当用户被禁用时，撤销其在 Redis 中登记的所有 JWT token / 会话
    if not payload.is_active:
        token_service = TokenRedisService(redis)
        await token_service.revoke_user_tokens(
            str(updated.id),
            reason="user_disabled_by_admin",
        )

    return _build_user_response(db, updated.id)


__all__ = ["router"]
