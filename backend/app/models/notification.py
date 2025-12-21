from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """系统通知（站内信/公告）。"""

    __tablename__ = "notifications"

    title: Mapped[str] = Column(String(200), nullable=False)
    content: Mapped[str] = Column(Text, nullable=False)
    level: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'info'"),
        default="info",
        doc="通知等级：info/success/warning/error",
    )
    target_type: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'all'"),
        default="all",
        doc="受众类型：all/users/roles",
    )
    target_user_ids = Column(
        JSONBCompat(),
        nullable=True,
        doc="当 target_type=users 时，包含目标用户 UUID 字符串列表",
    )
    target_role_codes = Column(
        JSONBCompat(),
        nullable=True,
        doc="当 target_type=roles 时，包含目标角色 code 列表",
    )
    link_url: Mapped[str | None] = Column(String(512), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
        default=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    creator: Mapped[User | None] = relationship("User")
    receipts: Mapped[list[NotificationReceipt]] = relationship(
        "NotificationReceipt",
        back_populates="notification",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class NotificationReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """用户阅读回执，用于标记已读状态。"""

    __tablename__ = "notification_receipts"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_notification_receipts_notification_user",
        ),
    )

    notification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    read_at = Column(DateTime(timezone=True), nullable=True)

    notification: Mapped[Notification] = relationship(
        "Notification", back_populates="receipts"
    )


__all__ = ["Notification", "NotificationReceipt"]
