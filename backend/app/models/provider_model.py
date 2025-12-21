from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint, text
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
    # 可选的「模型别名」，用于将长版本的上游模型 ID 映射为更易记的短名称。
    alias: Mapped[str | None] = Column(String(100), nullable=True)
    family: Mapped[str] = Column(String(50), nullable=False)
    display_name: Mapped[str] = Column(String(100), nullable=False)
    context_length: Mapped[int] = Column(Integer, nullable=False)
    capabilities = Column(JSONBCompat(), nullable=False)
    pricing = Column(JSONBCompat(), nullable=True)
    metadata_json = Column("metadata", JSONBCompat(), nullable=True)
    meta_hash: Mapped[str | None] = Column(String(64), nullable=True)
    disabled: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        doc="是否在该 Provider 下禁用该模型（禁用后不会参与路由与 /models 聚合）",
    )

    provider: Mapped[Provider] = relationship("Provider", back_populates="models")


__all__ = ["ProviderModel"]
