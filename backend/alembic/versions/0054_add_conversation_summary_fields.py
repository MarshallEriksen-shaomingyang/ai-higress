"""Add conversation summary fields.

Revision ID: 0054_add_conversation_summary_fields
Revises: 0053_add_images_generations_path_to_providers
Create Date: 2025-12-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0054_add_conversation_summary_fields"
down_revision = "0053_add_images_generations_path_to_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_conversations", sa.Column("summary_text", sa.Text(), nullable=True))
    op.add_column(
        "chat_conversations",
        sa.Column(
            "summary_until_sequence",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "chat_conversations",
        sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_conversations", "summary_updated_at")
    op.drop_column("chat_conversations", "summary_until_sequence")
    op.drop_column("chat_conversations", "summary_text")

