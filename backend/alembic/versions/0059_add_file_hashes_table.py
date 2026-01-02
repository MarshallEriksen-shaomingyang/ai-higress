"""Add file_hashes table for deduplication.

Revision ID: 0059_add_file_hashes_table
Revises: 0058_fix_audio_assets_timestamp_defaults
Create Date: 2026-01-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0059_add_file_hashes_table"
down_revision = "0058_fix_audio_assets_timestamp_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_hashes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False, comment="SHA-256 hash of file content"),
        sa.Column("file_type", sa.String(length=32), server_default=sa.text("'unknown'"), nullable=False, comment="File type: image, audio, etc."),
        sa.Column("owner_id", sa.UUID(), nullable=True, comment="Optional owner for user-scoped deduplication"),
        sa.Column("object_key", sa.String(length=2048), nullable=False, comment="Storage object key / path"),
        sa.Column("content_type", sa.String(length=128), server_default=sa.text("'application/octet-stream'"), nullable=False),
        sa.Column("size_bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reference_count", sa.Integer(), server_default=sa.text("1"), nullable=False, comment="Number of references to this file"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_file_hashes_content_hash"), "file_hashes", ["content_hash"], unique=False)
    op.create_index(op.f("ix_file_hashes_file_type"), "file_hashes", ["file_type"], unique=False)
    op.create_index(op.f("ix_file_hashes_owner_id"), "file_hashes", ["owner_id"], unique=False)
    op.create_index("ix_file_hashes_hash_type_owner", "file_hashes", ["content_hash", "file_type", "owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_file_hashes_hash_type_owner", table_name="file_hashes")
    op.drop_index(op.f("ix_file_hashes_owner_id"), table_name="file_hashes")
    op.drop_index(op.f("ix_file_hashes_file_type"), table_name="file_hashes")
    op.drop_index(op.f("ix_file_hashes_content_hash"), table_name="file_hashes")
    op.drop_table("file_hashes")
