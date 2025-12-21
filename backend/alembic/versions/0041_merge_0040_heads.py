"""Merge multiple Alembic heads.

This repository has two parallel migrations starting from 0039:
- 0040_add_disabled_to_provider_models
- 0040_partition_provider_routing_metrics_history_by_day

This merge revision makes `alembic upgrade head` unambiguous.
"""

from __future__ import annotations

revision = "0041_merge_0040_heads"
down_revision = (
    "0040_add_disabled_to_provider_models",
    "0040_partition_provider_routing_metrics_history_by_day",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

