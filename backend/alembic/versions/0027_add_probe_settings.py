"""Add provider probe settings and gateway probe prompt."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0027_add_probe_settings"
down_revision = "0026_add_provider_audit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column("probe_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "providers",
        sa.Column("probe_interval_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "providers",
        sa.Column("probe_model", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "gateway_config",
        sa.Column("probe_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gateway_config", "probe_prompt")
    op.drop_column("providers", "probe_model")
    op.drop_column("providers", "probe_interval_seconds")
    op.drop_column("providers", "probe_enabled")
