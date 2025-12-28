from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator


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


__all__ = ["JSONBCompat", "UTCDateTime"]
