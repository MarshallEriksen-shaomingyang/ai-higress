from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """针对单个用户的细粒度权限/配额配置."""

    __tablename__ = "user_permissions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "permission_type",
            name="uq_user_permissions_user_permission_type",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 例如：create_private_provider / submit_shared_provider / unlimited_providers / private_provider_limit
    permission_type: Mapped[str] = Column(String(32), nullable=False)
    # 对于配额类权限（如 private_provider_limit），保存在这里
    permission_value: Mapped[str | None] = Column(String(100), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = Column(Text, nullable=True)

    user: Mapped[User] = relationship("User")


__all__ = ["UserPermission"]

