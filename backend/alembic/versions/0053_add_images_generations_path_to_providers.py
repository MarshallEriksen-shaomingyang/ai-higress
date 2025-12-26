"""Add images_generations_path to providers and provider_presets.

Revision ID: 0053_add_images_generations_path_to_providers
Revises: 0052_create_chat_run_events
Create Date: 2025-12-26 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0053_add_images_generations_path_to_providers"
down_revision = "0052_create_chat_run_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column("images_generations_path", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "provider_presets",
        sa.Column("images_generations_path", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_presets", "images_generations_path")
    op.drop_column("providers", "images_generations_path")

