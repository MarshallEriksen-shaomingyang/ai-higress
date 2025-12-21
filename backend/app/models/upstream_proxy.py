from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship

from app.db.types import JSONBCompat

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UpstreamProxyConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    全局上游代理配置（管理员一套，服务全站）。

    说明：
    - 配置为“真相来源”（持久化），运行时可用代理集合由 Celery 任务写入 Redis；
    - enabled=false 时，网关不会从 Redis/数据库代理池取代理，保持直连。
    """

    __tablename__ = "upstream_proxy_config"

    enabled: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        doc="是否启用数据库/Redis 管理的代理池",
    )
    selection_strategy: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'random'"),
        default="random",
        doc="选择策略：random / round_robin（预留）",
    )
    failure_cooldown_seconds: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("120"),
        default=120,
        doc="代理失败后冷却时间（秒），冷却期内不会再被挑选",
    )
    healthcheck_url: Mapped[str] = Column(
        String(512),
        nullable=False,
        server_default=text("'https://ipv4.webshare.io/'"),
        default="https://ipv4.webshare.io/",
        doc="默认测活 URL（保证能出网）",
    )
    healthcheck_timeout_ms: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("5000"),
        default=5000,
        doc="默认测活超时（毫秒）",
    )
    healthcheck_method: Mapped[str] = Column(
        String(8),
        nullable=False,
        server_default=text("'GET'"),
        default="GET",
        doc="默认测活方法：GET/HEAD",
    )
    healthcheck_interval_seconds: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("300"),
        default=300,
        doc="单条代理的测活最小间隔（秒）",
    )


class UpstreamProxySource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    代理来源配置。

    type:
    - static_list: 管理员手动录入的代理条目；
    - remote_text_list: 从远程 URL 拉取文本列表（支持 ip:port / ip:port:user:pass / 完整 URL）。
    """

    __tablename__ = "upstream_proxy_sources"

    name: Mapped[str] = Column(String(100), nullable=False)
    source_type: Mapped[str] = Column(
        String(32),
        nullable=False,
        server_default=text("'static_list'"),
        default="static_list",
    )
    enabled: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )

    # Remote list only: encrypted to avoid leaking tokens embedded in URLs.
    remote_url_encrypted = Column(LargeBinary, nullable=True)
    remote_headers_encrypted = Column(LargeBinary, nullable=True)

    default_scheme: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'http'"),
        default="http",
        doc="解析简写代理行（如 ip:port）时使用的默认 scheme",
    )
    refresh_interval_seconds: Mapped[int | None] = Column(
        Integer,
        nullable=True,
        doc="远程列表刷新间隔（秒）；为空则使用全局默认",
    )
    last_refresh_at = Column(DateTime(timezone=True), nullable=True)
    last_refresh_error = Column(Text, nullable=True)

    # Optional overrides; when NULL, fallback to UpstreamProxyConfig defaults.
    healthcheck_url: Mapped[str | None] = Column(String(512), nullable=True)
    healthcheck_timeout_ms: Mapped[int | None] = Column(Integer, nullable=True)
    healthcheck_method: Mapped[str | None] = Column(String(8), nullable=True)

    # Future extension for remote list parsing.
    parse_hints = Column(
        JSONBCompat(),
        nullable=True,
        doc="解析提示（预留），用于支持更多远程列表格式",
    )

    endpoints: Mapped[list[UpstreamProxyEndpoint]] = relationship(
        "UpstreamProxyEndpoint",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UpstreamProxyEndpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    单条代理条目（规范化后的可连接信息）。

    注意：password 等敏感信息仅以加密形式存储；运行时写入 Redis 的同样是加密 token。
    """

    __tablename__ = "upstream_proxy_endpoints"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "identity_hash",
            name="uq_upstream_proxy_endpoints_source_identity",
        ),
    )

    source_id: Mapped[object] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("upstream_proxy_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[UpstreamProxySource] = relationship(
        "UpstreamProxySource",
        back_populates="endpoints",
    )

    scheme: Mapped[str] = Column(String(16), nullable=False)
    host: Mapped[str] = Column(String(255), nullable=False)
    port: Mapped[int] = Column(Integer, nullable=False)
    username: Mapped[str | None] = Column(String(255), nullable=True)
    password_encrypted = Column(LargeBinary, nullable=True)

    identity_hash: Mapped[str] = Column(
        String(64),
        nullable=False,
        index=True,
        doc="用于去重的稳定标识（HMAC-SHA256），避免把敏感字段用于唯一键",
    )

    enabled: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    # Health state (persisted; Redis stores the current 'available' set).
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    last_ok: Mapped[bool | None] = Column(Boolean, nullable=True)
    last_latency_ms: Mapped[float | None] = Column(Float, nullable=True)
    consecutive_failures: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    last_error = Column(Text, nullable=True)


__all__ = ["UpstreamProxyConfig", "UpstreamProxyEndpoint", "UpstreamProxySource"]
