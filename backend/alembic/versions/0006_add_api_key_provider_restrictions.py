"""Add API key provider restriction tables and flags."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_add_api_key_provider_restrictions"
down_revision = "0005_add_provider_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "has_provider_restrictions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    op.create_table(
        "api_key_allowed_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(("api_key_id",), ("api_keys.id",), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ("provider_id",),
            ("providers.provider_id",),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "api_key_id",
            "provider_id",
            name="uq_api_key_allowed_provider",
        ),
    )
    op.create_index(
        "ix_api_key_allowed_providers_api_key_id",
        "api_key_allowed_providers",
        ["api_key_id"],
        unique=False,
    )
    op.create_index(
        "ix_api_key_allowed_providers_provider_id",
        "api_key_allowed_providers",
        ["provider_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_api_key_allowed_providers_provider_id",
        table_name="api_key_allowed_providers",
    )
    op.drop_index(
        "ix_api_key_allowed_providers_api_key_id",
        table_name="api_key_allowed_providers",
    )
    op.drop_table("api_key_allowed_providers")
    op.drop_column("api_keys", "has_provider_restrictions")
