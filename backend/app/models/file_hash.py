from __future__ import annotations

from sqlalchemy import Column, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FileHash(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    文件哈希去重表。

    说明：
    - 用于存储文件内容的 SHA-256 哈希与存储路径的映射关系；
    - 上传文件前先查询哈希是否存在，存在则复用已有 object_key；
    - file_type 区分不同类型的文件（image, audio 等）；
    - owner_id 可选，用于按用户隔离去重（同一用户的重复文件复用）。
    """

    __tablename__ = "file_hashes"
    __table_args__ = (
        Index("ix_file_hashes_hash_type_owner", "content_hash", "file_type", "owner_id"),
    )

    content_hash: Mapped[str] = Column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of file content",
    )
    file_type: Mapped[str] = Column(
        String(32),
        nullable=False,
        index=True,
        server_default=text("'unknown'"),
        comment="File type: image, audio, etc.",
    )
    owner_id: Mapped[PG_UUID | None] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Optional owner for user-scoped deduplication",
    )
    object_key: Mapped[str] = Column(
        String(2048),
        nullable=False,
        comment="Storage object key / path",
    )
    content_type: Mapped[str] = Column(
        String(128),
        nullable=False,
        server_default=text("'application/octet-stream'"),
    )
    size_bytes: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    reference_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Number of references to this file",
    )


__all__ = ["FileHash"]
