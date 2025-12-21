"""Add approved_provider_uuid to provider_submissions for tracking."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017_add_approved_provider_to_submissions"
down_revision = "0016_add_billing_factor_to_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add approved_provider_uuid column to track which Provider was created from this submission
    op.add_column(
        "provider_submissions",
        sa.Column(
            "approved_provider_uuid",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_provider_submissions_approved_provider_uuid",
        "provider_submissions",
        ["approved_provider_uuid"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_provider_submissions_approved_provider_uuid_providers",
        "provider_submissions",
        "providers",
        ["approved_provider_uuid"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_provider_submissions_approved_provider_uuid_providers",
        "provider_submissions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_provider_submissions_approved_provider_uuid",
        table_name="provider_submissions",
    )
    op.drop_column("provider_submissions", "approved_provider_uuid")
