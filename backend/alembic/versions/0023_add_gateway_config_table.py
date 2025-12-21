"""Add gateway_config table for persistent gateway settings."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0023_add_gateway_config_table"
down_revision = "0022_add_provider_model_alias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gateway_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("api_base_url", sa.String(length=255), nullable=False),
        sa.Column("max_concurrent_requests", sa.Integer(), nullable=False),
        sa.Column("request_timeout_ms", sa.Integer(), nullable=False),
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("gateway_config")
