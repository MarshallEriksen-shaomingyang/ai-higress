"""Add idempotency_key to credit_transactions for async billing dedupe.

Revision ID: 0035_add_idempotency_key_to_credit_transactions
Revises: 0034_add_user_probe_tables
Create Date: 2025-12-15

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035_add_idempotency_key_to_credit_transactions"
down_revision = "0034_add_user_probe_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credit_transactions",
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ux_credit_transactions_idempotency_key",
        "credit_transactions",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_credit_transactions_idempotency_key", table_name="credit_transactions")
    op.drop_column("credit_transactions", "idempotency_key")

