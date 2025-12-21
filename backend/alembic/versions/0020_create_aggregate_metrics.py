"""
Revision ID: 0020_create_aggregate_metrics
Revises: 0019_add_api_key_status_fields
Create Date: 2025-02-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0020_create_aggregate_metrics"
down_revision = "0019_add_api_key_status_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aggregate_metrics",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("logical_model", sa.String(length=100), nullable=False),
        sa.Column("transport", sa.String(length=16), nullable=False, server_default=sa.text("'http'")),
        sa.Column("is_stream", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_duration", sa.Integer(), nullable=False, server_default=sa.text("300")),
        sa.Column("total_requests", sa.Integer(), nullable=False),
        sa.Column("success_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_p50_ms", sa.Float(), nullable=False),
        sa.Column("latency_p90_ms", sa.Float(), nullable=False),
        sa.Column("latency_p95_ms", sa.Float(), nullable=False),
        sa.Column("latency_p99_ms", sa.Float(), nullable=False),
        sa.Column("error_rate", sa.Float(), nullable=False),
        sa.Column("success_qps", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("recalculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_version", sa.String(length=32), nullable=False, server_default=sa.text("'offline-recalc'")),
    )

    op.create_index(
        "ix_aggregate_metrics_provider_logical_window",
        "aggregate_metrics",
        [
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
        ],
    )
    op.create_unique_constraint(
        "uq_aggregate_metrics_bucket",
        "aggregate_metrics",
        [
            "provider_id",
            "logical_model",
            "transport",
            "is_stream",
            "user_id",
            "api_key_id",
            "window_start",
            "window_duration",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_aggregate_metrics_bucket", "aggregate_metrics", type_="unique")
    op.drop_index("ix_aggregate_metrics_provider_logical_window", table_name="aggregate_metrics")
    op.drop_table("aggregate_metrics")
