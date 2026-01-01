from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AudioAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    用户语音输入资产（可复用）。

    说明：
    - object_key 指向本地/OSS/S3 的对象；
    - visibility:
      - private：仅 owner 可见/可引用
      - public：所有用户可见/可引用（“分享开关”打开）
    """

    __tablename__ = "audio_assets"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_audio_assets_object_key"),
    )

    owner_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[PG_UUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    object_key: Mapped[str] = Column(String(2048), nullable=False, index=True)
    filename: Mapped[str | None] = Column(String(512), nullable=True)
    display_name: Mapped[str | None] = Column(String(255), nullable=True)
    content_type: Mapped[str] = Column(String(128), nullable=False, server_default=text("'application/octet-stream'"))
    format: Mapped[str] = Column(String(16), nullable=False, server_default=text("'wav'"))
    size_bytes: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    visibility: Mapped[str] = Column(String(20), nullable=False, server_default=text("'private'"), index=True)


__all__ = ["AudioAsset"]

