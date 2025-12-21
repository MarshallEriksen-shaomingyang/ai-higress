from __future__ import annotations

from uuid import UUID as PyUUID

from sqlalchemy import Column, DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """用户提交用于加入全局池子的提供商配置."""

    __tablename__ = "provider_submissions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = Column(String(100), nullable=False)
    provider_id: Mapped[str] = Column(String(50), nullable=False)
    base_url: Mapped[str] = Column(String(255), nullable=False)
    provider_type: Mapped[str] = Column(String(16), nullable=False, default="native")
    encrypted_config: Mapped[str | None] = Column(Text, nullable=True)
    encrypted_api_key = Column(LargeBinary, nullable=True)
    description: Mapped[str | None] = Column(Text, nullable=True)

    # 审核状态：pending / testing / approved / approved_limited / rejected
    approval_status: Mapped[str] = Column(String(16), nullable=False, default="pending")
    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    review_notes: Mapped[str | None] = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # 关联到批准后创建的 Provider（用于取消提交时删除对应的公共 Provider）
    approved_provider_uuid: Mapped[PyUUID | None] = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped[User] = relationship("User", foreign_keys=[reviewed_by])
    approved_provider: Mapped[Provider | None] = relationship(
        "Provider", foreign_keys=[approved_provider_uuid]
    )


__all__ = ["ProviderSubmission"]
