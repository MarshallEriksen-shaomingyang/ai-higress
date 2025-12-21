"""Add provider_type column."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_add_provider_type"
down_revision = "0004_add_provider_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column(
            "provider_type",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'native'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("providers", "provider_type")
