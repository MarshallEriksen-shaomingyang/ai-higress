"""Create user routing metrics history table for per-user analytics."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0029_create_user_routing_metrics_history"
down_revision = "0028_add_provider_fields_to_credit_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_routing_metrics_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("logical_model", sa.String(length=100), nullable=False),
        sa.Column(
            "transport",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'http'"),
        ),
        sa.Column(
            "is_stream",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "window_duration",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column("total_requests", sa.Integer(), nullable=False),
        sa.Column(
            "success_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "error_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "latency_avg_ms",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("latency_p95_ms", sa.Float(), nullable=False),
        sa.Column("latency_p99_ms", sa.Float(), nullable=False),
        sa.Column(
            "error_rate",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_user_routing_metrics_history_user_window",
        "user_routing_metrics_history",
        ["user_id", "window_start"],
        unique=False,
    )
    op.create_index(
        "ix_user_routing_metrics_history_user_provider_window",
        "user_routing_metrics_history",
        ["user_id", "provider_id", "window_start"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_user_routing_metrics_history_bucket",
        "user_routing_metrics_history",
        [
            "user_id",
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "window_start",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_routing_metrics_history_bucket",
        "user_routing_metrics_history",
        type_="unique",
    )
    op.drop_index(
        "ix_user_routing_metrics_history_user_provider_window",
        table_name="user_routing_metrics_history",
    )
    op.drop_index(
        "ix_user_routing_metrics_history_user_window",
        table_name="user_routing_metrics_history",
    )
    op.drop_table("user_routing_metrics_history")
