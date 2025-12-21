"""Create rollup tables for provider routing metrics (hour/day).

These tables are populated by Celery scheduled tasks, and are used to serve
7d/30d dashboards efficiently without scanning minute-bucket history.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0038_create_provider_routing_metrics_rollups"
down_revision = "0037_add_metrics_retention_days_to_gateway_config"
branch_labels = None
depends_on = None


def _create_rollup_table(*, table_name: str, window_seconds: int, uq_name: str, ix_prefix: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("logical_model", sa.String(length=100), nullable=False),
        sa.Column("transport", sa.String(length=16), nullable=False, server_default=sa.text("'http'")),
        sa.Column("is_stream", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_duration", sa.Integer(), nullable=False, server_default=sa.text(str(window_seconds))),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_avg_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_p50_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_p95_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_p99_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_qps", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("error_4xx_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_5xx_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_429_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_timeout_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("input_tokens_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("token_estimated_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
            name=uq_name,
        ),
    )

    op.create_index(f"{ix_prefix}_provider_logical_window", table_name, ["provider_id", "logical_model", "transport", "is_stream", "window_start"])
    op.create_index(f"{ix_prefix}_user_window", table_name, ["user_id", "window_start"])
    op.create_index(f"{ix_prefix}_api_key_window", table_name, ["api_key_id", "window_start"])


def upgrade() -> None:
    _create_rollup_table(
        table_name="provider_routing_metrics_hourly",
        window_seconds=3600,
        uq_name="uq_provider_routing_metrics_hourly_bucket",
        ix_prefix="ix_provider_routing_metrics_hourly",
    )
    _create_rollup_table(
        table_name="provider_routing_metrics_daily",
        window_seconds=86400,
        uq_name="uq_provider_routing_metrics_daily_bucket",
        ix_prefix="ix_provider_routing_metrics_daily",
    )


def downgrade() -> None:
    op.drop_index("ix_provider_routing_metrics_daily_api_key_window", table_name="provider_routing_metrics_daily")
    op.drop_index("ix_provider_routing_metrics_daily_user_window", table_name="provider_routing_metrics_daily")
    op.drop_index("ix_provider_routing_metrics_daily_provider_logical_window", table_name="provider_routing_metrics_daily")
    op.drop_table("provider_routing_metrics_daily")

    op.drop_index("ix_provider_routing_metrics_hourly_api_key_window", table_name="provider_routing_metrics_hourly")
    op.drop_index("ix_provider_routing_metrics_hourly_user_window", table_name="provider_routing_metrics_hourly")
    op.drop_index("ix_provider_routing_metrics_hourly_provider_logical_window", table_name="provider_routing_metrics_hourly")
    op.drop_table("provider_routing_metrics_hourly")
