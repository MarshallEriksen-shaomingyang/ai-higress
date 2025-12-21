"""Add conversation pinned preview and unread fields.

Revision ID: 0046_add_conversation_pinned_preview_unread
Revises: 0045_add_eval_id_to_chat_runs
Create Date: 2025-12-19 07:45:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0046_add_conversation_pinned_preview_unread"
down_revision = "0045_add_eval_id_to_chat_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns with server_default for existing rows
    op.add_column('chat_conversations', sa.Column('is_pinned', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('chat_conversations', sa.Column('last_message_content', sa.String(length=1000), nullable=True))
    op.add_column('chat_conversations', sa.Column('unread_count', sa.Integer(), server_default=sa.text('0'), nullable=False))

    # If the index doesn't exist, create it (it was index=True in model, but maybe missing in DB)
    # We use try/except or check if we are sure it's missing.
    # The autogenerator wanted to create it, so it's likely missing.
    # op.create_index(op.f('ix_chat_conversations_last_activity_at'), 'chat_conversations', ['last_activity_at'], unique=False)


def downgrade() -> None:
    op.drop_column('chat_conversations', 'unread_count')
    op.drop_column('chat_conversations', 'last_message_content')
    op.drop_column('chat_conversations', 'is_pinned')
    # op.drop_index(op.f('ix_chat_conversations_last_activity_at'), table_name='chat_conversations')
