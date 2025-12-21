"""Add transport and is_stream dimensions to provider routing metrics history."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_add_transport_and_is_stream_to_metrics_history"
down_revision = "0009_extend_provider_routing_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增细分维度字段：transport（http/sdk）和 is_stream（是否流式）。
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "transport",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'http'"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "is_stream",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # 调整唯一约束，使时间桶在 (provider, logical_model, transport, is_stream, window_start)
    # 维度上唯一，便于分别统计 HTTP/SDK 和流式/非流式。
    op.drop_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        ["provider_id", "logical_model", "transport", "is_stream", "window_start"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        ["provider_id", "logical_model", "window_start"],
    )
    op.drop_column("provider_routing_metrics_history", "is_stream")
    op.drop_column("provider_routing_metrics_history", "transport")

