"""Add kb_global_embedding_model to gateway_config.

Revision ID: 0066_add_kb_global_embedding_model_to_gateway_config
Revises: 0065_add_memory_metrics_history_tables
Create Date: 2026-01-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0066_add_kb_global_embedding_model_to_gateway_config"
down_revision = "0065_add_memory_metrics_history_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gateway_config",
        sa.Column("kb_global_embedding_model", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gateway_config", "kb_global_embedding_model")

