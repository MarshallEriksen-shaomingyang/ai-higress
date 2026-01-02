from __future__ import annotations

from sqlalchemy import Column, String, Text

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SystemConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Generic system configuration (Key-Value storage).
    Used for runtime configurations that need to be dynamically adjustable
    without restarting the service, such as global embedding models, feature flags, etc.
    """

    __tablename__ = "system_configs"

    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)  # Stores the value as a string (or JSON string)
    description = Column(String(512), nullable=True)
    value_type = Column(String(50), nullable=False, default="string")  # string, int, bool, json

__all__ = ["SystemConfig"]
