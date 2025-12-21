from __future__ import annotations

from sqlalchemy import Column, String, Text
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """系统角色，用于按角色聚合权限。"""

    __tablename__ = "roles"

    code: Mapped[str] = Column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = Column(String(100), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)

    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )


__all__ = ["Role"]

