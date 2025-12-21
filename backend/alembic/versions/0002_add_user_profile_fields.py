"""Add user.display_name and user.avatar columns."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_add_user_profile_fields"
down_revision = "0001_create_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("avatar", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar")
    op.drop_column("users", "display_name")
