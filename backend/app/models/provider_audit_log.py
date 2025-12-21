from __future__ import annotations

from uuid import UUID as PyUUID

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderAuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """记录 Provider 审核与运营状态变更、测试等动作。"""

    __tablename__ = "provider_audit_logs"

    provider_uuid: Mapped[PyUUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = Column(String(32), nullable=False)
    from_status: Mapped[str | None] = Column(String(32), nullable=True)
    to_status: Mapped[str | None] = Column(String(32), nullable=True)
    operation_from_status: Mapped[str | None] = Column(String(16), nullable=True)
    operation_to_status: Mapped[str | None] = Column(String(16), nullable=True)
    operator_id: Mapped[PyUUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    remark: Mapped[str | None] = Column(Text, nullable=True)
    test_record_uuid: Mapped[PyUUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("provider_test_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider = relationship("Provider", back_populates="audit_logs")
    operator = relationship("User")
    test_record = relationship("ProviderTestRecord")


__all__ = ["ProviderAuditLog"]
