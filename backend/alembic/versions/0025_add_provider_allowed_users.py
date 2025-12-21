"""Add provider_allowed_users table for per-user sharing."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0025_add_provider_allowed_users"
down_revision = "0024_add_notifications_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_allowed_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "provider_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "provider_uuid",
            "user_id",
            name="uq_provider_allowed_user",
        ),
    )
    op.create_index(
        "ix_provider_allowed_users_provider_uuid",
        "provider_allowed_users",
        ["provider_uuid"],
    )
    op.create_index(
        "ix_provider_allowed_users_user_id",
        "provider_allowed_users",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_allowed_users_user_id",
        table_name="provider_allowed_users",
    )
    op.drop_index(
        "ix_provider_allowed_users_provider_uuid",
        table_name="provider_allowed_users",
    )
    op.drop_table("provider_allowed_users")
