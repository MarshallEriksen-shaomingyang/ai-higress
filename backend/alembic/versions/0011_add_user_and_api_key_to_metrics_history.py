"""Add user and api_key dimensions to provider routing metrics history."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011_add_user_and_api_key_to_metrics_history"
down_revision = "0010_add_transport_and_is_stream_to_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "api_key_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_provider_routing_metrics_history_user_id",
        "provider_routing_metrics_history",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_routing_metrics_history_api_key_id",
        "provider_routing_metrics_history",
        ["api_key_id"],
        unique=False,
    )

    # 调整唯一约束，加入 user_id / api_key_id 维度，支持按用户/API Key 统计。
    op.drop_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_routing_metrics_history_bucket",
        "provider_routing_metrics_history",
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


def downgrade() -> None:
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
    op.drop_index(
        "ix_provider_routing_metrics_history_api_key_id",
        table_name="provider_routing_metrics_history",
    )
    op.drop_index(
        "ix_provider_routing_metrics_history_user_id",
        table_name="provider_routing_metrics_history",
    )
    op.drop_column("provider_routing_metrics_history", "api_key_id")
    op.drop_column("provider_routing_metrics_history", "user_id")

