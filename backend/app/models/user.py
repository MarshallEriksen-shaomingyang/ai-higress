from __future__ import annotations

from sqlalchemy import Boolean, Column, String, Text, text
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System user who can own multiple identities."""

    __tablename__ = "users"

    username: Mapped[str] = Column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = Column(String(255), nullable=True)
    avatar: Mapped[str | None] = Column(String(512), nullable=True)
    hashed_password: Mapped[str] = Column(Text, nullable=False)
    is_active: Mapped[bool] = Column(Boolean, server_default=text("TRUE"), nullable=False)
    is_superuser: Mapped[bool] = Column(Boolean, server_default=text("FALSE"), nullable=False)

    identities: Mapped[list["Identity"]] = relationship(
        "Identity",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )


__all__ = ["User"]
