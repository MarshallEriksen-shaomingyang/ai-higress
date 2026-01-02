from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.db.types import JSONBCompat
from app.db.types import UUIDCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KBAttribute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Deterministic structured attributes extracted from chat.

    Design notes:
    - Use `subject_id` as the unique subject key to avoid NULL-unique pitfalls across DBs.
      Examples:
        - user:<user_uuid>
        - project:<api_key_uuid> (MVP project_id == api_key_id)
        - system:global (reserved)
    """

    __tablename__ = "kb_attributes"
    __table_args__ = (
        UniqueConstraint("subject_id", "key", name="uq_kb_attributes_subject_key"),
        Index("ix_kb_attributes_subject_updated", "subject_id", "updated_at"),
        Index("ix_kb_attributes_owner_user", "owner_user_id"),
        Index("ix_kb_attributes_project", "project_id"),
    )

    # NOTE: Use UUIDCompat so tests can run on SQLite without UUID/int coercion issues.
    id = Column(UUIDCompat(), primary_key=True, default=uuid.uuid4, nullable=False)

    subject_id: Mapped[str] = Column(String(80), nullable=False, index=True)

    # Optional split fields for filtering/debugging.
    owner_user_id: Mapped[UUID | None] = Column(
        UUIDCompat(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[UUID | None] = Column(
        UUIDCompat(),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="MVP project_id == api_key_id",
    )

    scope: Mapped[str] = Column(String(16), nullable=False, doc="user|project|system")
    category: Mapped[str] = Column(String(32), nullable=False, doc="preference|constraint|config")
    key: Mapped[str] = Column(String(160), nullable=False, index=True)
    value = Column(JSONBCompat(), nullable=False)

    confidence: Mapped[float | None] = Column(Float, nullable=True)
    source_conversation_id: Mapped[UUID | None] = Column(
        UUIDCompat(),
        ForeignKey("chat_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_until_sequence: Mapped[int | None] = Column(Integer, nullable=True)


__all__ = ["KBAttribute"]
