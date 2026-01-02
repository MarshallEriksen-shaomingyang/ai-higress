from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator
from uuid import UUID as PyUUID
import uuid as _uuid


class JSONBCompat(TypeDecorator):
    """JSONB 类型在 PostgreSQL 以外回退为通用 JSON。"""

    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UTCDateTime(TypeDecorator):
    """
    DateTime(timezone=True) 的跨方言兼容：
    - Postgres：原生时区支持，统一转为 UTC。
    - SQLite：通常返回 naive datetime；这里默认按 UTC 解释并补齐 tzinfo。
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, dt.datetime):
            return value
        if value.tzinfo is None:
            # 约定：naive 视为 UTC
            return value
        as_utc = value.astimezone(dt.UTC)
        if dialect.name == "postgresql":
            return as_utc
        # SQLite 等：存为 naive（UTC）
        return as_utc.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, dt.datetime):
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)


class UUIDCompat(TypeDecorator):
    """
    UUID type that works across PostgreSQL and SQLite test environments.

    - PostgreSQL: uses native UUID(as_uuid=True)
    - Others (e.g. SQLite): stores as string (36 chars)
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, PyUUID):
            # PostgreSQL native driver accepts UUID objects when as_uuid=True.
            if dialect.name == "postgresql":
                return value
            return str(value)
        # Allow passing string UUIDs.
        if isinstance(value, str):
            v = value.strip()
            if not v:
                return None
            try:
                parsed = PyUUID(v)
            except Exception:
                return v
            return parsed if dialect.name == "postgresql" else str(parsed)
        # As a fallback, accept int-form UUIDs from some adapters.
        if isinstance(value, int):
            parsed = _uuid.UUID(int=int(value))
            return parsed if dialect.name == "postgresql" else str(parsed)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, PyUUID):
            return value
        if isinstance(value, int):
            return _uuid.UUID(int=int(value))
        if isinstance(value, (bytes, bytearray)):
            b = bytes(value)
            if len(b) == 16:
                return _uuid.UUID(bytes=b)
            try:
                return PyUUID(b.decode("utf-8", errors="ignore"))
            except Exception:
                return None
        if isinstance(value, str):
            try:
                return PyUUID(value)
            except Exception:
                return None
        return None


__all__ = ["JSONBCompat", "UTCDateTime", "UUIDCompat"]
