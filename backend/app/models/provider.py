from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .provider_allowed_user import ProviderAllowedUser
from .provider_preset import ProviderPreset


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Database model storing provider metadata and configuration."""

    __tablename__ = "providers"

    provider_id: Mapped[str] = Column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = Column(String(100), nullable=False)
    base_url: Mapped[str] = Column(String(255), nullable=False)
    transport: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'http'"),
        default="http",
        doc="传输类型：http（标准HTTP）、sdk（官方SDK）、claude_cli（Claude CLI伪装）",
    )
    provider_type: Mapped[str] = Column(
        String(16), nullable=False, server_default=text("'native'"), default="native"
    )
    sdk_vendor: Mapped[str | None] = Column(
        String(32),
        nullable=True,
        doc="When transport='sdk', identifies which official SDK implementation to use (e.g. openai/google/claude/vertexai).",
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
    models_path: Mapped[str | None] = Column(String(100), nullable=True)
    messages_path: Mapped[str | None] = Column(String(100), nullable=True)
    chat_completions_path: Mapped[str | None] = Column(String(100), nullable=True)
    responses_path: Mapped[str | None] = Column(String(100), nullable=True)
    images_generations_path: Mapped[str | None] = Column(String(100), nullable=True)
    static_models = Column(JSONBCompat(), nullable=True)
    supported_api_styles = Column(JSONBCompat(), nullable=True)
    status: Mapped[str] = Column(String(16), nullable=False, server_default=text("'healthy'"))
    audit_status: Mapped[str] = Column(
        String(24),
        nullable=False,
        server_default=text("'pending'"),
        default="pending",
        doc="审核状态：pending/testing/approved/rejected/approved_limited",
    )
    operation_status: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'active'"),
        default="active",
        doc="运营状态：active/paused/offline",
    )
    probe_enabled: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
        doc="是否开启自动探针/巡检",
    )
    probe_interval_seconds: Mapped[int | None] = Column(
        Integer,
        nullable=True,
        doc="自定义探针/巡检间隔（秒），为空则使用全局默认",
    )
    probe_model: Mapped[str | None] = Column(
        String(100),
        nullable=True,
        doc="探针使用的模型 ID（可选）",
    )
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

    api_keys: Mapped[list[ProviderAPIKey]] = relationship(
        "ProviderAPIKey",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    models: Mapped[list[ProviderModel]] = relationship(
        "ProviderModel",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    api_key_restrictions: Mapped[list[APIKeyAllowedProvider]] = relationship(
        "APIKeyAllowedProvider",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    shared_users: Mapped[list[ProviderAllowedUser]] = relationship(
        "ProviderAllowedUser",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    owner: Mapped[User] = relationship("User")
    preset: Mapped[ProviderPreset | None] = relationship(
        "ProviderPreset", back_populates="providers", foreign_keys=[preset_uuid]
    )
    audit_logs: Mapped[list[ProviderAuditLog]] = relationship(
        "ProviderAuditLog",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    test_records: Mapped[list[ProviderTestRecord]] = relationship(
        "ProviderTestRecord",
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
