"""Add composite indexes for metrics history queries.

Dashboard queries frequently filter by (user_id, window_start) or
(api_key_id, window_start) with a time range. Composite indexes help avoid
large scans when the metrics history table grows.
"""

from __future__ import annotations

from alembic import op

revision = "0039_add_composite_indexes_for_metrics_history"
down_revision = "0038_create_provider_routing_metrics_rollups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_provider_routing_metrics_history_user_window",
        "provider_routing_metrics_history",
        ["user_id", "window_start"],
        unique=False,
    )
    op.create_index(
        "ix_provider_routing_metrics_history_api_key_window",
        "provider_routing_metrics_history",
        ["api_key_id", "window_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_routing_metrics_history_api_key_window",
        table_name="provider_routing_metrics_history",
    )
    op.drop_index(
        "ix_provider_routing_metrics_history_user_window",
        table_name="provider_routing_metrics_history",
    )

