"""Widen alembic_version.version_num to 128 chars

Revision ID: 0030_widen_alembic_version_num
Revises: 0029_create_user_routing_metrics_history
Create Date: 2025-02-11
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0030_widen_alembic_version_num"
down_revision = "0029_create_user_routing_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.VARCHAR(),  # tolerate existing length
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=128),
        type_=sa.VARCHAR(length=32),
        existing_nullable=False,
    )
