"""Add disabled flag to provider_models.

This enables per-provider model disabling so that a provider owner can
temporarily remove a single upstream model from routing and /models
aggregation without deleting the model row.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0040_add_disabled_to_provider_models"
down_revision = "0039_add_composite_indexes_for_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_models",
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("provider_models", "disabled")

