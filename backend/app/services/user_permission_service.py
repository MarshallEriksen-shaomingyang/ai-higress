from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Permission, RolePermission, UserPermission, UserRole
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
        direct_stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.permission_type == permission_type,
            or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
        )
        if self.session.execute(direct_stmt).scalars().first() is not None:
            return True

        # 2. 再看用户所属角色是否包含该权限代码
        role_stmt = (
            select(RolePermission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(UserRole.user_id == user_id, Permission.code == permission_type)
            .limit(1)
        )
        return self.session.execute(role_stmt).first() is not None

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
            stmt_all = select(Permission.code)
            codes = self.session.execute(stmt_all).scalars().all()
            # 去重 + 排序，方便前端展示
            return sorted(set(codes))

        now = datetime.now(UTC)

        # 1. 用户直挂权限
        direct_stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
            UserPermission.user_id == user_id,
            or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
        )
        direct_records = list(self.session.execute(direct_stmt).scalars().all())
        direct_codes = {rec.permission_type for rec in direct_records}

        # 2. 角色上的权限
        role_codes_stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        )
        role_codes = set(self.session.execute(role_codes_stmt).scalars().all())

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
        stmt_unlimited = select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.permission_type == "unlimited_providers",
            or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
        )
        if self.session.execute(stmt_unlimited).scalars().first() is not None:
            return None

        # 然后检查自定义配额
        stmt_limit = select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.permission_type == "private_provider_limit",
            or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
        )
        record = self.session.execute(stmt_limit).scalars().first()
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
        stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
            UserPermission.user_id == user_id
        )
        return list(self.session.execute(stmt).scalars().all())

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

        # 尝试获取已有记录（唯一约束保证最多一条）
        stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.permission_type == permission_type,
        )
        record = self.session.execute(stmt).scalars().first()
        if record is None:
            record = UserPermission(
                user_id=user_id,
                permission_type=permission_type,
                permission_value=permission_value,
                expires_at=expires_at,
                notes=notes,
            )
            self.session.add(record)
        else:
            record.permission_value = permission_value
            record.expires_at = expires_at
            if notes is not None:
                record.notes = notes

        self.session.commit()
        self.session.refresh(record)
        return record

    def revoke_permission(self, permission_id: UUID) -> None:
        """撤销一条权限记录."""

        record = self.session.get(UserPermission, permission_id)
        if record is None:
            return
        self.session.delete(record)
        self.session.commit()


__all__ = ["UserPermissionService", "UserPermissionServiceError"]
