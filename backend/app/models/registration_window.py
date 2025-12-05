import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer
from sqlalchemy.orm import Mapped

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RegistrationWindowStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"


class RegistrationWindow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "registration_windows"

    start_time: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    max_registrations: Mapped[int] = Column(Integer, nullable=False)
    registered_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    auto_activate: Mapped[bool] = Column(Boolean, nullable=False, default=True)
    status: Mapped[RegistrationWindowStatus] = Column(
        Enum(RegistrationWindowStatus, native_enum=False),
        nullable=False,
        default=RegistrationWindowStatus.SCHEDULED,
    )


__all__ = ["RegistrationWindow", "RegistrationWindowStatus"]
