"""add api key status fields

Revision ID: 0019_add_api_key_status_fields
Revises: 0018_add_registration_windows
Create Date: 2025-02-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0019_add_api_key_status_fields"
down_revision = "0018_add_registration_windows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
    )
    op.add_column(
        "api_keys",
        sa.Column("disabled_reason", sa.String(length=64), nullable=True),
    )
    op.execute("UPDATE api_keys SET is_active = TRUE WHERE is_active IS NULL")


def downgrade() -> None:
    op.drop_column("api_keys", "disabled_reason")
    op.drop_column("api_keys", "is_active")
