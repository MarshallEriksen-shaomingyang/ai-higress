"""Add audio_assets table.

Revision ID: 0057_add_audio_assets_table
Revises: 0056_add_user_risk_fields
Create Date: 2026-01-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0057_add_audio_assets_table"
down_revision = "0056_add_user_risk_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audio_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("object_key", sa.String(length=2048), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), server_default="application/octet-stream", nullable=False),
        sa.Column("format", sa.String(length=16), server_default="wav", nullable=False),
        sa.Column("size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("visibility", sa.String(length=20), server_default="private", nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_audio_assets_object_key"),
    )
    op.create_index(op.f("ix_audio_assets_conversation_id"), "audio_assets", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_audio_assets_object_key"), "audio_assets", ["object_key"], unique=False)
    op.create_index(op.f("ix_audio_assets_owner_id"), "audio_assets", ["owner_id"], unique=False)
    op.create_index(op.f("ix_audio_assets_visibility"), "audio_assets", ["visibility"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audio_assets_visibility"), table_name="audio_assets")
    op.drop_index(op.f("ix_audio_assets_owner_id"), table_name="audio_assets")
    op.drop_index(op.f("ix_audio_assets_object_key"), table_name="audio_assets")
    op.drop_index(op.f("ix_audio_assets_conversation_id"), table_name="audio_assets")
    op.drop_table("audio_assets")

