from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Identity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """External identity mapping for a user (e.g. OAuth provider)."""

    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_identity_provider_external"),
    )

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = Column(String(50), nullable=False)
    external_id: Mapped[str] = Column(String(255), nullable=False)
    display_name: Mapped[str | None] = Column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="identities")


__all__ = ["Identity"]
