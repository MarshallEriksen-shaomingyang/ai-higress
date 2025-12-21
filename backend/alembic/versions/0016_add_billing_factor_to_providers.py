"""Add billing_factor column to providers

用于在计费时区分不同 Provider 的成本系数：
- 1.0 代表基准价格；
- >1.0 代表更贵的 Provider；
- <1.0 代表更便宜或折扣 Provider。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_add_billing_factor_to_providers"
down_revision = "0015_add_credit_and_billing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column(
            "billing_factor",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("providers", "billing_factor")

