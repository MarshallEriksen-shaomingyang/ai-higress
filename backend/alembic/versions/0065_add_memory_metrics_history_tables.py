"""Add memory_metrics_history and memory_metrics_hourly tables.

Revision ID: 0065_add_memory_metrics_history_tables
Revises: 0064_add_system_configs_table
Create Date: 2026-01-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0065_add_memory_metrics_history_tables"
down_revision = "0064_add_system_configs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create memory_metrics_history table (minute granularity)
    op.create_table(
        "memory_metrics_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Dimension fields
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("window_duration", sa.Integer(), nullable=False, server_default=sa.text("60")),
        # Request counts
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Retrieval metrics
        sa.Column("retrieval_triggered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_empty", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_error", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Hit rate metrics
        sa.Column("memory_hits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("memory_misses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Latency metrics
        sa.Column("retrieval_latency_sum_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_latency_avg_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_latency_p50_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_latency_p95_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_latency_p99_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        # Query rewrite metrics
        sa.Column("rewrite_triggered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rewrite_success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rewrite_latency_sum_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        # Embedding metrics
        sa.Column("embedding_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("embedding_latency_sum_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        # Vector search metrics
        sa.Column("vector_search_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("vector_search_latency_sum_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("raw_hits_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("valid_hits_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Routing metrics
        sa.Column("routing_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("routing_stored_user", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("routing_stored_system", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("routing_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("routing_latency_sum_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        # Session/backlog metrics
        sa.Column("session_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("backlog_batches_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("backlog_batches_max", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Computed rates
        sa.Column("trigger_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("hit_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_backlog_per_session", sa.Float(), nullable=False, server_default=sa.text("0")),
    )

    # Create unique constraint for upsert
    op.create_unique_constraint(
        "uq_memory_metrics_history_bucket",
        "memory_metrics_history",
        ["user_id", "project_id", "window_start"],
    )

    # Create additional indexes for efficient querying
    op.create_index(
        "ix_memory_metrics_history_user_window",
        "memory_metrics_history",
        ["user_id", "window_start"],
    )
    op.create_index(
        "ix_memory_metrics_history_project_window",
        "memory_metrics_history",
        ["project_id", "window_start"],
    )

    # Create memory_metrics_hourly table (hourly rollup)
    op.create_table(
        "memory_metrics_hourly",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Dimension fields
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("window_duration", sa.Integer(), nullable=False, server_default=sa.text("3600")),
        # Aggregated counts
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_triggered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_empty", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_error", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("memory_hits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("memory_misses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Aggregated latencies
        sa.Column("retrieval_latency_avg_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("retrieval_latency_p95_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        # Routing aggregates
        sa.Column("routing_requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("routing_stored_user", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("routing_stored_system", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Session/backlog aggregates
        sa.Column("session_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("backlog_batches_sum", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("backlog_batches_max", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Computed rates
        sa.Column("trigger_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("hit_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_backlog_per_session", sa.Float(), nullable=False, server_default=sa.text("0")),
    )

    # Create unique constraint for hourly table
    op.create_unique_constraint(
        "uq_memory_metrics_hourly_bucket",
        "memory_metrics_hourly",
        ["user_id", "project_id", "window_start"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_memory_metrics_hourly_bucket", "memory_metrics_hourly", type_="unique")
    op.drop_table("memory_metrics_hourly")

    op.drop_index("ix_memory_metrics_history_project_window", table_name="memory_metrics_history")
    op.drop_index("ix_memory_metrics_history_user_window", table_name="memory_metrics_history")
    op.drop_constraint("uq_memory_metrics_history_bucket", "memory_metrics_history", type_="unique")
    op.drop_table("memory_metrics_history")
