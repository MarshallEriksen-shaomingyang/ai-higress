"""Fix audio_assets timestamp server defaults.

Revision ID: 0058_fix_audio_assets_timestamp_defaults
Revises: 0057_add_audio_assets_table
Create Date: 2026-01-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0058_fix_audio_assets_timestamp_defaults"
down_revision = "0057_add_audio_assets_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server default for created_at
    op.alter_column(
        "audio_assets",
        "created_at",
        server_default=sa.text("now()"),
    )
    # Add server default for updated_at
    op.alter_column(
        "audio_assets",
        "updated_at",
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    # Remove server defaults
    op.alter_column(
        "audio_assets",
        "updated_at",
        server_default=None,
    )
    op.alter_column(
        "audio_assets",
        "created_at",
        server_default=None,
    )
