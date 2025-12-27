from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import UserPermission
from app.repositories.user_permission_repository import (
    delete_user_permission as repo_delete_user_permission,
    get_private_provider_limit_record,
    has_direct_permission,
    has_role_permission,
    has_unlimited_providers,
    list_all_permission_codes,
    list_direct_permission_types,
    list_role_permission_codes,
    list_user_permissions as repo_list_user_permissions,
    upsert_user_permission as repo_upsert_user_permission,
)
from app.services.user_service import get_user_by_id
from app.settings import settings


class UserPermissionServiceError(RuntimeError):
    """Base error for user permission operations."""


class UserPermissionService:
    """用户权限及配额相关的查询和写入逻辑."""

    def __init__(self, session: Session):
        self.session = session

    # ---- 查询能力 ----

    def has_permission(self, user_id: UUID, permission_type: str) -> bool:
        """检查用户是否拥有指定权限（角色 + 用户直挂）。

        优先级：
        - 超级用户默认拥有所有权限；
        - 用户直接授予的 `UserPermission` 记录；
        - 用户所属角色 `UserRole` 上绑定的 `RolePermission` 所关联的 `Permission.code`。
        """
        user = get_user_by_id(self.session, user_id)
        if user is None:
            return False
        if user.is_superuser:
            return True

        # 1. 先看用户是否有直挂的有效权限记录（支持 expires_at）
        now = datetime.now(UTC)
        if has_direct_permission(self.session, user_id=user_id, permission_type=permission_type, now=now):
            return True

        # 2. 再看用户所属角色是否包含该权限代码
        return has_role_permission(self.session, user_id=user_id, permission_code=permission_type)

    def get_effective_permission_codes(self, user_id: UUID) -> list[str]:
        """返回用户当前生效的权限编码列表（角色 + 用户直挂）。

        - 对于超级用户：返回系统中所有已定义的 Permission.code；
        - 对于普通用户：返回
          * 未过期的 UserPermission.permission_type
          * 以及其角色上的 Permission.code。
        """
        user = get_user_by_id(self.session, user_id)
        if user is None:
            return []

        # 超级用户：拥有所有权限，直接列出所有 Permission.code
        if user.is_superuser:
            codes = list_all_permission_codes(self.session)
            # 去重 + 排序，方便前端展示
            return sorted(set(codes))

        now = datetime.now(UTC)

        # 1. 用户直挂权限
        direct_codes = list_direct_permission_types(self.session, user_id=user_id, now=now)

        # 2. 角色上的权限
        role_codes = list_role_permission_codes(self.session, user_id=user_id)

        return sorted(direct_codes | role_codes)

    def get_provider_limit(self, user_id: UUID) -> int | None:
        """获取用户可创建私有提供商的数量上限。

        - 超级用户: 无限制，返回 None
        - 拥有 unlimited_providers: 返回 None
        - 拥有 private_provider_limit: 使用该值
        - 否则: 使用系统默认值
        """
        user = get_user_by_id(self.session, user_id)
        if user is None:
            return settings.default_user_private_provider_limit
        if user.is_superuser:
            return None

        now = datetime.now(UTC)

        # 优先检查 unlimited_providers
        if has_unlimited_providers(self.session, user_id=user_id, now=now):
            return None

        # 然后检查自定义配额
        record = get_private_provider_limit_record(self.session, user_id=user_id, now=now)
        if record and record.permission_value:
            try:
                return int(record.permission_value)
            except ValueError:
                logger.warning(
                    "Invalid permission_value for private_provider_limit: %r",
                    record.permission_value,
                )

        return settings.default_user_private_provider_limit

    def get_user_permissions(self, user_id: UUID) -> list[UserPermission]:
        """列出用户当前所有权限记录。"""
        return repo_list_user_permissions(self.session, user_id=user_id)

    # ---- 写操作 ----

    def grant_permission(
        self,
        user_id: UUID,
        permission_type: str,
        permission_value: str | None = None,
        expires_at: datetime | None = None,
        notes: str | None = None,
    ) -> UserPermission:
        """授予或更新用户的某一类权限."""

        return repo_upsert_user_permission(
            self.session,
            user_id=user_id,
            permission_type=permission_type,
            permission_value=permission_value,
            expires_at=expires_at,
            notes=notes,
        )

    def revoke_permission(self, permission_id: UUID) -> None:
        """撤销一条权限记录."""
        repo_delete_user_permission(self.session, permission_id=permission_id)


__all__ = ["UserPermissionService", "UserPermissionServiceError"]
