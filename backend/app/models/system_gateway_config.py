from __future__ import annotations

from sqlalchemy import Column, Integer, String

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GatewayConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Persistent gateway configuration exposed to end users.

    This table is intended to store a single row with the current
    gateway configuration. Environment variables provide initial
    defaults, but the effective values are persisted here so that
    admin changes survive process restarts and are shared across
    instances.
    """

    __tablename__ = "gateway_config"

    api_base_url = Column(String(255), nullable=False)
    max_concurrent_requests = Column(Integer, nullable=False)
    request_timeout_ms = Column(Integer, nullable=False)
    cache_ttl_seconds = Column(Integer, nullable=False)


__all__ = ["GatewayConfig"]

