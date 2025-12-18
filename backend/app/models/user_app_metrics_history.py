from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserAppRequestMetricsHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Per-user app usage metrics aggregated into minute buckets.

    该表用于回答“某个用户最近主要用哪些客户端/应用在调用网关”之类的管理需求，
    聚合维度尽量保持粗粒度，避免高基数导致存储膨胀。
    """

    __tablename__ = "user_app_request_metrics_history"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "app_name",
            "window_start",
            name="uq_user_app_request_metrics_history_bucket",
        ),
        Index(
            "ix_user_app_request_metrics_history_user_window",
            "user_id",
            "window_start",
        ),
        Index(
            "ix_user_app_request_metrics_history_user_app_window",
            "user_id",
            "app_name",
            "window_start",
        ),
    )

    user_id: Mapped[PG_UUID] = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[PG_UUID | None] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    app_name: Mapped[str] = Column(
        String(120),
        nullable=False,
        index=True,
    )
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_duration: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("60"),
    )
    total_requests: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )


__all__ = ["UserAppRequestMetricsHistory"]

