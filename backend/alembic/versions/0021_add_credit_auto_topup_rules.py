"""Add credit_auto_topup_rules table for per-user auto top-up configuration."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0021_add_credit_auto_topup_rules"
down_revision = "0020_create_aggregate_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_auto_topup_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("min_balance_threshold", sa.Integer(), nullable=False),
        sa.Column("target_balance", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
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
        sa.ForeignKeyConstraint(("user_id",), ("users.id",), ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_credit_auto_topup_rules_user_id"),
    )
    op.create_index(
        "ix_credit_auto_topup_rules_user_id",
        "credit_auto_topup_rules",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_credit_auto_topup_rules_user_id",
        table_name="credit_auto_topup_rules",
    )
    op.drop_table("credit_auto_topup_rules")

