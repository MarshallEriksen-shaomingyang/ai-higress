"""Add provider routing metrics history table for analytics."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_add_provider_routing_metrics_history"
down_revision = "0007_add_provider_submission_and_user_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_routing_metrics_history",
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
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("logical_model", sa.String(length=100), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "window_duration",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column("latency_p95_ms", sa.Float(), nullable=False),
        sa.Column("latency_p99_ms", sa.Float(), nullable=False),
        sa.Column("error_rate", sa.Float(), nullable=False),
        sa.Column("success_qps_1m", sa.Float(), nullable=False),
        sa.Column("total_requests_1m", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
    )
    op.create_index(
        "ix_provider_routing_metrics_history_provider_id",
        "provider_routing_metrics_history",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_routing_metrics_history_logical_model",
        "provider_routing_metrics_history",
        ["logical_model"],
        unique=False,
    )
    op.create_index(
        "ix_provider_routing_metrics_history_window_start",
        "provider_routing_metrics_history",
        ["window_start"],
        unique=False,
    )
    op.create_index(
        "ix_provider_routing_metrics_history_provider_logical_window",
        "provider_routing_metrics_history",
        ["provider_id", "logical_model", "window_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_routing_metrics_history_provider_logical_window",
        table_name="provider_routing_metrics_history",
    )
    op.drop_index(
        "ix_provider_routing_metrics_history_window_start",
        table_name="provider_routing_metrics_history",
    )
    op.drop_index(
        "ix_provider_routing_metrics_history_logical_model",
        table_name="provider_routing_metrics_history",
    )
    op.drop_index(
        "ix_provider_routing_metrics_history_provider_id",
        table_name="provider_routing_metrics_history",
    )
    op.drop_table("provider_routing_metrics_history")

