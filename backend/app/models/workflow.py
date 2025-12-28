from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    用户可复用的工作流模版（SOP / Spec）。

    - spec_json 为前端编辑器产物（结构化 JSON）。
    - 运行时会复制一份快照到 WorkflowRun.workflow_snapshot，避免模版被修改影响历史运行。
    """

    __tablename__ = "workflows"
    __table_args__ = (
        Index("ix_workflows_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = Column(String(200), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    spec_json = Column(JSONBCompat(), nullable=False)


__all__ = ["Workflow"]

