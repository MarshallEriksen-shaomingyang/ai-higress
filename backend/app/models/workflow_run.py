from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    工作流一次执行实例（运行快照 + 状态机）。
    """

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_user_created", "user_id", "created_at"),
        Index("ix_workflow_runs_workflow_created", "workflow_id", "created_at"),
        Index("ix_workflow_runs_status_updated", "status", "updated_at"),
    )

    workflow_id: Mapped[PG_UUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'paused'"),
        default="paused",
    )
    paused_reason: Mapped[str | None] = Column(String(64), nullable=True)
    current_step_index: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"), default=0)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True)

    error_code: Mapped[str | None] = Column(String(64), nullable=True)
    error_message: Mapped[str | None] = Column(Text, nullable=True)

    workflow_snapshot = Column(JSONBCompat(), nullable=False)
    steps_state = Column(JSONBCompat(), nullable=False, server_default=text("'{}'"))


__all__ = ["WorkflowRun"]

