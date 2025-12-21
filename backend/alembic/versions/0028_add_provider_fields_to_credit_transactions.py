"""Add provider metadata columns to credit transactions"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0028_add_provider_fields_to_credit_transactions"
down_revision = "0027_add_probe_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credit_transactions",
        sa.Column("provider_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "credit_transactions",
        sa.Column("provider_model_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_credit_transactions_provider_id",
        "credit_transactions",
        ["provider_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_credit_transactions_provider_id_providers",
        "credit_transactions",
        "providers",
        ["provider_id"],
        ["provider_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_credit_transactions_provider_id_providers",
        "credit_transactions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_credit_transactions_provider_id",
        table_name="credit_transactions",
    )
    op.drop_column("credit_transactions", "provider_model_id")
    op.drop_column("credit_transactions", "provider_id")
