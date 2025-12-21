from __future__ import annotations

from sqlalchemy import Column, String, Text, text
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderPreset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """管理员维护的官方 Provider 预设配置。"""

    __tablename__ = "provider_presets"

    preset_id: Mapped[str] = Column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = Column(String(100), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    provider_type: Mapped[str] = Column(
        String(16), nullable=False, server_default=text("'native'"), default="native"
    )
    transport: Mapped[str] = Column(
        String(16), nullable=False, server_default=text("'http'"), default="http"
    )
    sdk_vendor: Mapped[str | None] = Column(
        String(32),
        nullable=True,
        doc="When transport='sdk', identifies which official SDK implementation to use (e.g. openai/google/claude/vertexai).",
    )
    base_url: Mapped[str] = Column(String(255), nullable=False)
    models_path: Mapped[str | None] = Column(String(100), nullable=True)
    chat_completions_path: Mapped[str | None] = Column(String(100), nullable=True)
    messages_path: Mapped[str | None] = Column(String(100), nullable=True)
    responses_path: Mapped[str | None] = Column(String(100), nullable=True)
    supported_api_styles = Column(JSONBCompat(), nullable=True)
    retryable_status_codes = Column(JSONBCompat(), nullable=True)
    custom_headers = Column(JSONBCompat(), nullable=True)
    static_models = Column(JSONBCompat(), nullable=True)
    metadata_json = Column("metadata", JSONBCompat(), nullable=True)

    providers: Mapped[list[Provider]] = relationship(
        "Provider",
        back_populates="preset",
        foreign_keys="Provider.preset_uuid",
        cascade="save-update",
    )


__all__ = ["ProviderPreset"]
