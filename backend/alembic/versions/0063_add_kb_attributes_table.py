"""Add kb_attributes table for deterministic structured memory.

Revision ID: 0063_add_kb_attributes_table
Revises: 0062_add_conversation_memory_cursor
Create Date: 2026-01-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0063_add_kb_attributes_table"
down_revision = "0062_add_conversation_memory_cursor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("subject_id", sa.String(length=80), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_until_sequence", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_conversation_id"], ["chat_conversations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("subject_id", "key", name="uq_kb_attributes_subject_key"),
    )
    op.create_index("ix_kb_attributes_subject_updated", "kb_attributes", ["subject_id", "updated_at"])
    op.create_index("ix_kb_attributes_owner_user", "kb_attributes", ["owner_user_id"])
    op.create_index("ix_kb_attributes_project", "kb_attributes", ["project_id"])
    op.create_index("ix_kb_attributes_subject_id", "kb_attributes", ["subject_id"])
    op.create_index("ix_kb_attributes_key", "kb_attributes", ["key"])


def downgrade() -> None:
    op.drop_index("ix_kb_attributes_key", table_name="kb_attributes")
    op.drop_index("ix_kb_attributes_subject_id", table_name="kb_attributes")
    op.drop_index("ix_kb_attributes_project", table_name="kb_attributes")
    op.drop_index("ix_kb_attributes_owner_user", table_name="kb_attributes")
    op.drop_index("ix_kb_attributes_subject_updated", table_name="kb_attributes")
    op.drop_table("kb_attributes")

