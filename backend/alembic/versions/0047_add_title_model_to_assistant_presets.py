"""Add title_logical_model to assistant presets.

Revision ID: 0047_add_title_model_to_assistant_presets
Revises: 0046_add_conversation_pinned_preview_unread
Create Date: 2025-12-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0047_add_title_model_to_assistant_presets"
down_revision = "0046_add_conversation_pinned_preview_unread"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_presets",
        sa.Column("title_logical_model", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assistant_presets", "title_logical_model")

