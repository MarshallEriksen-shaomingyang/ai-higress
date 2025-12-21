"""Add project chat settings to api keys.

Revision ID: 0048_add_project_chat_settings_to_api_keys
Revises: 0047_add_title_model_to_assistant_presets
Create Date: 2025-12-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0048_add_project_chat_settings_to_api_keys"
down_revision = "0047_add_title_model_to_assistant_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("chat_default_logical_model", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("chat_title_logical_model", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "chat_title_logical_model")
    op.drop_column("api_keys", "chat_default_logical_model")

