"""
文件哈希去重服务。

提供统一的文件内容哈希计算、查询和注册功能，
用于在存储文件前检查是否已存在相同内容的文件。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file_hash import FileHash

if TYPE_CHECKING:
    pass


FileType = Literal["image", "audio", "document", "unknown"]


@dataclass(frozen=True, slots=True)
class ExistingFile:
    """已存在的文件信息。"""

    object_key: str
    content_type: str
    size_bytes: int
    file_hash_id: UUID


def compute_content_hash(data: bytes) -> str:
    """
    计算文件内容的 SHA-256 哈希值。

    Args:
        data: 文件二进制内容

    Returns:
        64 字符的十六进制哈希字符串
    """
    return hashlib.sha256(data).hexdigest()


def find_existing_file(
    db: Session,
    content_hash: str,
    file_type: FileType,
    *,
    owner_id: UUID | str | None = None,
) -> ExistingFile | None:
    """
    查找是否已存在相同哈希的文件。

    Args:
        db: 数据库会话
        content_hash: 文件内容的 SHA-256 哈希
        file_type: 文件类型
        owner_id: 可选的所有者 ID（用于用户级别的去重隔离）

    Returns:
        如果存在则返回 ExistingFile，否则返回 None
    """
    stmt = select(FileHash).where(
        FileHash.content_hash == content_hash,
        FileHash.file_type == file_type,
    )

    if owner_id is not None:
        owner_uuid = UUID(str(owner_id)) if isinstance(owner_id, str) else owner_id
        stmt = stmt.where(FileHash.owner_id == owner_uuid)
    else:
        stmt = stmt.where(FileHash.owner_id.is_(None))

    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return None

    return ExistingFile(
        object_key=row.object_key,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        file_hash_id=row.id,
    )


def register_file_hash(
    db: Session,
    content_hash: str,
    file_type: FileType,
    object_key: str,
    content_type: str,
    size_bytes: int,
    *,
    owner_id: UUID | str | None = None,
) -> FileHash:
    """
    注册新的文件哈希记录。

    Args:
        db: 数据库会话
        content_hash: 文件内容的 SHA-256 哈希
        file_type: 文件类型
        object_key: 存储对象的 key/路径
        content_type: MIME 类型
        size_bytes: 文件大小（字节）
        owner_id: 可选的所有者 ID

    Returns:
        创建的 FileHash 记录
    """
    owner_uuid: UUID | None = None
    if owner_id is not None:
        owner_uuid = UUID(str(owner_id)) if isinstance(owner_id, str) else owner_id

    record = FileHash(
        content_hash=content_hash,
        file_type=file_type,
        owner_id=owner_uuid,
        object_key=object_key,
        content_type=content_type,
        size_bytes=size_bytes,
        reference_count=1,
    )
    db.add(record)
    db.flush()
    return record


def increment_reference_count(db: Session, file_hash_id: UUID) -> None:
    """
    增加文件哈希的引用计数。

    Args:
        db: 数据库会话
        file_hash_id: FileHash 记录 ID
    """
    stmt = select(FileHash).where(FileHash.id == file_hash_id).with_for_update()
    row = db.execute(stmt).scalar_one_or_none()
    if row is not None:
        row.reference_count = (row.reference_count or 1) + 1
        db.flush()


def check_and_register_file(
    db: Session,
    data: bytes,
    file_type: FileType,
    object_key: str,
    content_type: str,
    *,
    owner_id: UUID | str | None = None,
) -> tuple[ExistingFile | None, str]:
    """
    检查文件是否已存在，如果不存在则注册新记录。

    这是一个便捷方法，组合了 compute_content_hash、find_existing_file 和 register_file_hash。

    Args:
        db: 数据库会话
        data: 文件二进制内容
        file_type: 文件类型
        object_key: 如果是新文件，使用的存储 object_key
        content_type: MIME 类型
        owner_id: 可选的所有者 ID

    Returns:
        (existing_file, content_hash) 元组：
        - 如果文件已存在，existing_file 包含已有文件信息
        - 如果是新文件，existing_file 为 None，同时会创建新的 FileHash 记录
        - content_hash 始终返回计算出的哈希值
    """
    content_hash = compute_content_hash(data)

    existing = find_existing_file(db, content_hash, file_type, owner_id=owner_id)
    if existing is not None:
        increment_reference_count(db, existing.file_hash_id)
        return existing, content_hash

    register_file_hash(
        db,
        content_hash=content_hash,
        file_type=file_type,
        object_key=object_key,
        content_type=content_type,
        size_bytes=len(data),
        owner_id=owner_id,
    )
    return None, content_hash


__all__ = [
    "ExistingFile",
    "FileType",
    "check_and_register_file",
    "compute_content_hash",
    "find_existing_file",
    "increment_reference_count",
    "register_file_hash",
]
