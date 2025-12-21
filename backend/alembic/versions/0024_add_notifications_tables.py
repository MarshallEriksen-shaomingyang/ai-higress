"""Create notifications and notification_receipts tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024_add_notifications_tables"
down_revision = "0023_add_gateway_config_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "level",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'info'"),
        ),
        sa.Column(
            "target_type",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'all'"),
        ),
        sa.Column("target_user_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("target_role_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("link_url", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
    )
    op.create_index(
        "ix_notifications_expires_at",
        "notifications",
        ["expires_at"],
    )
    op.create_index(
        "ix_notifications_created_by",
        "notifications",
        ["created_by"],
    )

    op.create_table(
        "notification_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
            "notification_id",
            "user_id",
            name="uq_notification_receipts_notification_user",
        ),
    )
    op.create_index(
        "ix_notification_receipts_notification_id",
        "notification_receipts",
        ["notification_id"],
    )
    op.create_index(
        "ix_notification_receipts_user_id",
        "notification_receipts",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_receipts_user_id", table_name="notification_receipts")
    op.drop_index(
        "ix_notification_receipts_notification_id", table_name="notification_receipts"
    )
    op.drop_table("notification_receipts")

    op.drop_index("ix_notifications_created_by", table_name="notifications")
    op.drop_index("ix_notifications_expires_at", table_name="notifications")
    op.drop_table("notifications")
