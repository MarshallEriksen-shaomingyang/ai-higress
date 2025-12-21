from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class APIKeyAllowedProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Association table linking API keys to the providers they may access."""

    __tablename__ = "api_key_allowed_providers"
    __table_args__ = (
        UniqueConstraint(
            "api_key_id",
            "provider_id",
            name="uq_api_key_allowed_provider",
        ),
    )

    api_key_id = Column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str] = Column(
        String(50),
        ForeignKey("providers.provider_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    api_key: Mapped[APIKey] = relationship(
        "APIKey",
        back_populates="allowed_provider_links",
    )
    provider: Mapped[Provider] = relationship(
        "Provider",
        back_populates="api_key_restrictions",
    )


__all__ = ["APIKeyAllowedProvider"]
