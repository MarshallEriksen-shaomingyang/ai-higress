from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowRunEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    WorkflowRun 执行过程中的不可变事件（append-only）。

    用途：
    - SSE replay（断线重连回放）
    - 审计/排障（工具链路可追溯）
    """

    __tablename__ = "workflow_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_workflow_run_events_run_seq"),
        Index("ix_workflow_run_events_run_created", "run_id", "created_at"),
    )

    run_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    event_type: Mapped[str] = Column(String(64), nullable=False)
    payload: Mapped[dict] = Column(JSONBCompat(), nullable=False, server_default=text("'{}'"))


__all__ = ["WorkflowRunEvent"]

