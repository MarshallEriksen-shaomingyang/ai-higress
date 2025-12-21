"""Add dashboard v2 fields to provider routing metrics history.

Adds:
- latency_p50_ms
- token aggregates (input/output/total + estimated count)
- error breakdown counts (4xx/5xx/429/timeout)
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0036_add_dashboard_v2_metrics_fields"
down_revision = "0035_add_idempotency_key_to_credit_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "latency_p50_ms",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "input_tokens_sum",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "output_tokens_sum",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "total_tokens_sum",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "token_estimated_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "error_4xx_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "error_5xx_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "error_429_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "provider_routing_metrics_history",
        sa.Column(
            "error_timeout_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("provider_routing_metrics_history", "error_timeout_requests")
    op.drop_column("provider_routing_metrics_history", "error_429_requests")
    op.drop_column("provider_routing_metrics_history", "error_5xx_requests")
    op.drop_column("provider_routing_metrics_history", "error_4xx_requests")
    op.drop_column("provider_routing_metrics_history", "token_estimated_requests")
    op.drop_column("provider_routing_metrics_history", "total_tokens_sum")
    op.drop_column("provider_routing_metrics_history", "output_tokens_sum")
    op.drop_column("provider_routing_metrics_history", "input_tokens_sum")
    op.drop_column("provider_routing_metrics_history", "latency_p50_ms")

