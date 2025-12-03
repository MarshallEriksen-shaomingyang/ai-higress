from __future__ import annotations

from sqlalchemy import Column, String, Text
from sqlalchemy.orm import Mapped

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Permission definition that can later be assigned to users or roles."""

    __tablename__ = "permissions"

    code: Mapped[str] = Column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = Column(Text, nullable=True)


__all__ = ["Permission"]
