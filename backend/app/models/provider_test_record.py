from __future__ import annotations

from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderTestRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """存储审核/巡检测试记录。"""

    __tablename__ = "provider_test_records"

    provider_uuid: Mapped[PyUUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'auto'"),
        default="auto",
        doc="auto/custom/cron",
    )
    success: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )
    summary: Mapped[str | None] = Column(Text, nullable=True)
    probe_results = Column(JSONBCompat(), nullable=True)
    latency_ms: Mapped[int | None] = Column(Integer, nullable=True)
    error_code: Mapped[str | None] = Column(String(64), nullable=True)
    cost: Mapped[float | None] = Column(Float, nullable=True)
    started_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)

    provider = relationship("Provider", back_populates="test_records")


__all__ = ["ProviderTestRecord"]
