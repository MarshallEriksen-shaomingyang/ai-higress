from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship
from uuid import UUID

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .provider_preset import ProviderPreset
from .provider_allowed_user import ProviderAllowedUser


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
    sdk_vendor: Mapped[str | None] = Column(
        String(32),
        nullable=True,
        doc="When transport='sdk', identifies which official SDK implementation to use (e.g. openai/google/claude).",
    )
    weight: Mapped[float] = Column(Float, nullable=False, server_default=text("1.0"))
    region: Mapped[str | None] = Column(String(50), nullable=True)
    cost_input: Mapped[float | None] = Column(Float, nullable=True)
    cost_output: Mapped[float | None] = Column(Float, nullable=True)
    billing_factor: Mapped[float] = Column(
        Float,
        nullable=False,
        server_default=text("1.0"),
    )
    max_qps: Mapped[int | None] = Column(Integer, nullable=True)
    retryable_status_codes = Column(JSONBCompat(), nullable=True)
    custom_headers = Column(JSONBCompat(), nullable=True)
    models_path: Mapped[str] = Column(String(100), nullable=False, server_default=text("'/v1/models'"))
    messages_path: Mapped[str | None] = Column(String(100), nullable=True)
    chat_completions_path: Mapped[str] = Column(
        String(100), nullable=False, server_default=text("'/v1/chat/completions'"), default="/v1/chat/completions"
    )
    responses_path: Mapped[str | None] = Column(String(100), nullable=True)
    static_models = Column(JSONBCompat(), nullable=True)
    supported_api_styles = Column(JSONBCompat(), nullable=True)
    status: Mapped[str] = Column(String(16), nullable=False, server_default=text("'healthy'"))
    last_check = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSONBCompat(), nullable=True)

    # Ownership and visibility metadata.
    # When owner_id is NULL and visibility is "public", the provider is part of
    # the global shared pool. When owner_id is set and visibility is "private",
    # the provider is a user-scoped private provider.
    owner_id: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    preset_uuid: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("provider_presets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visibility: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'public'"),
        default="public",
    )

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
    shared_users: Mapped[list["ProviderAllowedUser"]] = relationship(
        "ProviderAllowedUser",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    owner: Mapped["User"] = relationship("User")
    preset: Mapped[ProviderPreset | None] = relationship(
        "ProviderPreset", back_populates="providers", foreign_keys=[preset_uuid]
    )

    @property
    def preset_id(self) -> str | None:
        if self.preset is None:
            return None
        return self.preset.preset_id

    @property
    def shared_user_ids(self) -> list[UUID]:
        """辅助属性：返回已授权的用户 ID 列表。"""
        return [link.user_id for link in self.shared_users or []]


__all__ = ["Provider"]
