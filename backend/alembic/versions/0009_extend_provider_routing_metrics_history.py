"""Extend provider routing metrics history with counters and avg latency."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_extend_provider_routing_metrics_history"
down_revision = "0008_add_provider_routing_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 基础计数和平均延迟字段，便于逐条请求累计更新。
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "success_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "error_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "latency_avg_ms",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # 为按分钟桶做 UPSERT，增加唯一约束。
    op.create_unique_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        ["provider_id", "logical_model", "window_start"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        type_="unique",
    )
    op.drop_column("provider_routing_metrics_history", "latency_avg_ms")
    op.drop_column("provider_routing_metrics_history", "error_requests")
    op.drop_column("provider_routing_metrics_history", "success_requests")

