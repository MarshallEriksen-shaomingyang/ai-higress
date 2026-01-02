"""Add conversation memory extraction cursor.

Revision ID: 0062_add_conversation_memory_cursor
Revises: 0061_add_kb_memory_router_model_to_api_keys
Create Date: 2026-01-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0062_add_conversation_memory_cursor"
down_revision = "0061_add_kb_memory_router_model_to_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column(
            "last_memory_extracted_sequence",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_conversations", "last_memory_extracted_sequence")

