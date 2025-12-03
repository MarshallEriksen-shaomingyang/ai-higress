from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-provider model metadata stored in the database."""

    __tablename__ = "provider_models"
    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_models_provider_model"),
    )

    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = Column(String(100), nullable=False)
    family: Mapped[str] = Column(String(50), nullable=False)
    display_name: Mapped[str] = Column(String(100), nullable=False)
    context_length: Mapped[int] = Column(Integer, nullable=False)
    capabilities = Column(JSONBCompat(), nullable=False)
    pricing = Column(JSONBCompat(), nullable=True)
    metadata_json = Column("metadata", JSONBCompat(), nullable=True)
    meta_hash: Mapped[str | None] = Column(String(64), nullable=True)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="models")


__all__ = ["ProviderModel"]
