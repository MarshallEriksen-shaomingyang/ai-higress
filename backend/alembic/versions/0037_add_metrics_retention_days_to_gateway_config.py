"""Add metrics_retention_days to gateway_config.

This setting controls how many days of minute-bucket metrics history we keep
in the database for dashboard/reporting usage.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0037_add_metrics_retention_days_to_gateway_config"
down_revision = "0036_add_dashboard_v2_metrics_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gateway_config",
        sa.Column(
            "metrics_retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("15"),
        ),
    )


def downgrade() -> None:
    op.drop_column("gateway_config", "metrics_retention_days")

