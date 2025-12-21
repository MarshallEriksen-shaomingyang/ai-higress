"""Add upstream proxy management tables

Revision ID: 0031_add_upstream_proxy_management
Revises: 0030_widen_alembic_version_num
Create Date: 2025-12-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0031_add_upstream_proxy_management"
down_revision = "0030_widen_alembic_version_num"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upstream_proxy_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "fallback_to_env",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "selection_strategy",
            sa.String(length=16),
            server_default=sa.text("'random'"),
            nullable=False,
        ),
        sa.Column(
            "failure_cooldown_seconds",
            sa.Integer(),
            server_default=sa.text("120"),
            nullable=False,
        ),
        sa.Column(
            "healthcheck_url",
            sa.String(length=512),
            server_default=sa.text("'https://ipv4.webshare.io/'"),
            nullable=False,
        ),
        sa.Column(
            "healthcheck_timeout_ms",
            sa.Integer(),
            server_default=sa.text("5000"),
            nullable=False,
        ),
        sa.Column(
            "healthcheck_method",
            sa.String(length=8),
            server_default=sa.text("'GET'"),
            nullable=False,
        ),
        sa.Column(
            "healthcheck_interval_seconds",
            sa.Integer(),
            server_default=sa.text("300"),
            nullable=False,
        ),
    )

    op.create_table(
        "upstream_proxy_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "source_type",
            sa.String(length=32),
            server_default=sa.text("'static_list'"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("remote_url_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("remote_headers_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "default_scheme",
            sa.String(length=16),
            server_default=sa.text("'http'"),
            nullable=False,
        ),
        sa.Column("refresh_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_error", sa.Text(), nullable=True),
        sa.Column("healthcheck_url", sa.String(length=512), nullable=True),
        sa.Column("healthcheck_timeout_ms", sa.Integer(), nullable=True),
        sa.Column("healthcheck_method", sa.String(length=8), nullable=True),
        sa.Column("parse_hints", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_upstream_proxy_sources_enabled",
        "upstream_proxy_sources",
        ["enabled"],
    )
    op.create_index(
        "ix_upstream_proxy_sources_source_type",
        "upstream_proxy_sources",
        ["source_type"],
    )

    op.create_table(
        "upstream_proxy_endpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("upstream_proxy_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheme", sa.String(length=16), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok", sa.Boolean(), nullable=True),
        sa.Column("last_latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "source_id",
            "identity_hash",
            name="uq_upstream_proxy_endpoints_source_identity",
        ),
    )
    op.create_index(
        "ix_upstream_proxy_endpoints_source_id",
        "upstream_proxy_endpoints",
        ["source_id"],
    )
    op.create_index(
        "ix_upstream_proxy_endpoints_identity_hash",
        "upstream_proxy_endpoints",
        ["identity_hash"],
    )
    op.create_index(
        "ix_upstream_proxy_endpoints_enabled",
        "upstream_proxy_endpoints",
        ["enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_upstream_proxy_endpoints_enabled", table_name="upstream_proxy_endpoints")
    op.drop_index("ix_upstream_proxy_endpoints_identity_hash", table_name="upstream_proxy_endpoints")
    op.drop_index("ix_upstream_proxy_endpoints_source_id", table_name="upstream_proxy_endpoints")
    op.drop_table("upstream_proxy_endpoints")

    op.drop_index("ix_upstream_proxy_sources_source_type", table_name="upstream_proxy_sources")
    op.drop_index("ix_upstream_proxy_sources_enabled", table_name="upstream_proxy_sources")
    op.drop_table("upstream_proxy_sources")

    op.drop_table("upstream_proxy_config")

