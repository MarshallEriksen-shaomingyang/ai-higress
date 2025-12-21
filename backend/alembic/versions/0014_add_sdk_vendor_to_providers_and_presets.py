"""Add sdk_vendor column to providers and provider_presets

This makes SDK vendor selection explicit instead of relying on provider id / host heuristics.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_add_sdk_vendor_to_providers_and_presets"
down_revision = "0013_add_provider_presets_and_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column("sdk_vendor", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "provider_presets",
        sa.Column("sdk_vendor", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_presets", "sdk_vendor")
    op.drop_column("providers", "sdk_vendor")

