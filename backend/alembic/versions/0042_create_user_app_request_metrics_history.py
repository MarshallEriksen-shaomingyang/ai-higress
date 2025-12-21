"""Create user app request metrics history table for per-user app usage analytics."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0042_create_user_app_request_metrics_history"
down_revision = "0041_merge_0040_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_app_request_metrics_history",
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
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("app_name", sa.String(length=120), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "window_duration",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column(
            "total_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_user_app_request_metrics_history_user_window",
        "user_app_request_metrics_history",
        ["user_id", "window_start"],
        unique=False,
    )
    op.create_index(
        "ix_user_app_request_metrics_history_user_app_window",
        "user_app_request_metrics_history",
        ["user_id", "app_name", "window_start"],
        unique=False,
    )
    op.create_index(
        "ix_user_app_request_metrics_history_api_key_id",
        "user_app_request_metrics_history",
        ["api_key_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_user_app_request_metrics_history_bucket",
        "user_app_request_metrics_history",
        ["user_id", "app_name", "window_start"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_app_request_metrics_history_bucket",
        "user_app_request_metrics_history",
        type_="unique",
    )
    op.drop_index(
        "ix_user_app_request_metrics_history_api_key_id",
        table_name="user_app_request_metrics_history",
    )
    op.drop_index(
        "ix_user_app_request_metrics_history_user_app_window",
        table_name="user_app_request_metrics_history",
    )
    op.drop_index(
        "ix_user_app_request_metrics_history_user_window",
        table_name="user_app_request_metrics_history",
    )
    op.drop_table("user_app_request_metrics_history")

