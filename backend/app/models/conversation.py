from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """按助手分组的会话。"""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index(
            "ix_chat_conversations_user_assistant_last_activity",
            "user_id",
            "assistant_id",
            "last_activity_at",
        ),
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
    assistant_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("assistant_presets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = Column(String(255), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=False, index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    is_pinned: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    last_message_content: Mapped[str | None] = Column(Text, nullable=True)
    unread_count: Mapped[int] = Column(Integer, default=0, nullable=False)

    summary_text: Mapped[str | None] = Column(Text, nullable=True, doc="会话摘要（用户可见、可编辑）")
    summary_until_sequence: Mapped[int] = Column(
        Integer,
        default=0,
        nullable=False,
        doc="摘要覆盖到的最后一条消息序号（含）；0 表示未启用摘要",
    )
    summary_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="摘要最后更新时间（UTC）",
    )

    last_memory_extracted_sequence: Mapped[int] = Column(
        Integer,
        default=0,
        nullable=False,
        doc="聊天记忆（Qdrant）旁路抽取已处理到的最后一条消息序号（含）；0 表示未处理过",
    )


__all__ = ["Conversation"]
