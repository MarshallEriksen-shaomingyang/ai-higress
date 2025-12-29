from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, text
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

    risk_score: Mapped[int] = Column(Integer, nullable=False, server_default=text("0"))
    risk_level: Mapped[str] = Column(
        String(20),
        nullable=False,
        server_default=text("'low'"),
        index=True,
    )
    risk_remark: Mapped[str | None] = Column(Text, nullable=True)
    risk_updated_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)

    identities: Mapped[list[Identity]] = relationship(
        "Identity",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list[APIKey]] = relationship(
        "APIKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    credit_account: Mapped[CreditAccount] = relationship(
        "CreditAccount",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


__all__ = ["User"]
