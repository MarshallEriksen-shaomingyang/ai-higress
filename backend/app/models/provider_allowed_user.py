from __future__ import annotations

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderAllowedUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """关联表：将 Provider 授权给指定用户使用."""

    __tablename__ = "provider_allowed_users"
    __table_args__ = (
        UniqueConstraint(
            "provider_uuid",
            "user_id",
            name="uq_provider_allowed_user",
        ),
    )

    provider_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[Provider] = relationship(
        "Provider",
        back_populates="shared_users",
    )
    user: Mapped[User] = relationship("User")


__all__ = ["ProviderAllowedUser"]
