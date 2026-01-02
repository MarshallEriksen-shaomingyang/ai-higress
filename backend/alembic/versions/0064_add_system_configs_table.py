"""Add system_configs table for dynamic runtime configuration.

Revision ID: 0064_add_system_configs_table
Revises: 0063_add_kb_attributes_table
Create Date: 2026-01-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0064_add_system_configs_table"
down_revision = "0063_add_kb_attributes_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("value_type", sa.String(length=50), nullable=False, server_default=sa.text("'string'")),
        sa.UniqueConstraint("key", name="uq_system_configs_key"),
    )
    op.create_index("ix_system_configs_key", "system_configs", ["key"])


def downgrade() -> None:
    op.drop_index("ix_system_configs_key", table_name="system_configs")
    op.drop_table("system_configs")
