from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import UserPermission
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
        """检查用户是否拥有指定权限。

        超级用户默认拥有所有权限。
        """
        user = get_user_by_id(self.session, user_id)
        if user is None:
            return False
        if user.is_superuser:
            return True

        now = datetime.now(timezone.utc)
        stmt: Select[tuple[UserPermission]] = select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.permission_type == permission_type,
            or_(UserPermission.expires_at.is_(None), UserPermission.expires_at > now),
        )
        return self.session.execute(stmt).scalars().first() is not None

    def get_provider_limit(self, user_id: UUID) -> Optional[int]:
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

        now = datetime.now(timezone.utc)

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

