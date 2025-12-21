from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Run(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一条 user message 在某逻辑模型上的执行记录。"""

    __tablename__ = "chat_runs"
    __table_args__ = (
        Index("ix_chat_runs_message_created", "message_id", "created_at"),
        Index("ix_chat_runs_user_created", "user_id", "created_at"),
    )

    eval_id: Mapped[PG_UUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_evals.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
        doc="可选：所属评测（Eval）。用于在 challenger 完成后高效更新 Eval 状态。",
    )
    message_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="MVP project_id == api_key_id",
    )
    requested_logical_model: Mapped[str] = Column(String(128), nullable=False)
    selected_provider_id: Mapped[str | None] = Column(String(64), nullable=True)
    selected_provider_model: Mapped[str | None] = Column(String(128), nullable=True)

    status: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'queued'"),
        default="queued",
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = Column(Integer, nullable=True)
    cost_credits: Mapped[int | None] = Column(Integer, nullable=True)
    error_code: Mapped[str | None] = Column(String(64), nullable=True)
    error_message: Mapped[str | None] = Column(String(512), nullable=True)

    request_payload = Column(JSONBCompat(), nullable=True)
    response_payload = Column(JSONBCompat(), nullable=True)
    output_text: Mapped[str | None] = Column(Text, nullable=True)
    output_preview: Mapped[str | None] = Column(String(400), nullable=True)


__all__ = ["Run"]
