from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderAPIKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encrypted API key belonging to a provider."""

    __tablename__ = "provider_api_keys"

    provider_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encrypted_key = Column(LargeBinary, nullable=False)
    weight: Mapped[float] = Column(Float, nullable=False, default=1.0)
    max_qps: Mapped[int | None] = Column(Integer, nullable=True)
    label: Mapped[str | None] = Column(String(50), nullable=True)
    status: Mapped[str] = Column(String(20), nullable=False, default="active")

    provider: Mapped["Provider"] = relationship("Provider", back_populates="api_keys")


__all__ = ["ProviderAPIKey"]
