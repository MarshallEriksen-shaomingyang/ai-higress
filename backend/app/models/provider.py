from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Database model storing provider metadata and configuration."""

    __tablename__ = "providers"

    provider_id: Mapped[str] = Column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = Column(String(100), nullable=False)
    base_url: Mapped[str] = Column(String(255), nullable=False)
    transport: Mapped[str] = Column(String(16), nullable=False, server_default=text("'http'"))
    provider_type: Mapped[str] = Column(
        String(16), nullable=False, server_default=text("'native'"), default="native"
    )
    weight: Mapped[float] = Column(Float, nullable=False, server_default=text("1.0"))
    region: Mapped[str | None] = Column(String(50), nullable=True)
    cost_input: Mapped[float | None] = Column(Float, nullable=True)
    cost_output: Mapped[float | None] = Column(Float, nullable=True)
    max_qps: Mapped[int | None] = Column(Integer, nullable=True)
    retryable_status_codes = Column(JSONBCompat(), nullable=True)
    custom_headers = Column(JSONBCompat(), nullable=True)
    models_path: Mapped[str] = Column(String(100), nullable=False, server_default=text("'/v1/models'"))
    messages_path: Mapped[str | None] = Column(String(100), nullable=True)
    static_models = Column(JSONBCompat(), nullable=True)
    status: Mapped[str] = Column(String(16), nullable=False, server_default=text("'healthy'"))
    last_check = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSONBCompat(), nullable=True)

    api_keys: Mapped[list["ProviderAPIKey"]] = relationship(
        "ProviderAPIKey",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    models: Mapped[list["ProviderModel"]] = relationship(
        "ProviderModel",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    api_key_restrictions: Mapped[list["APIKeyAllowedProvider"]] = relationship(
        "APIKeyAllowedProvider",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


__all__ = ["Provider"]
