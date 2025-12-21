"""Add provider submissions and user permissions, extend providers with ownership."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_add_provider_submission_and_user_permissions"
down_revision = "0006_add_api_key_provider_restrictions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend providers with ownership and visibility.
    op.add_column(
        "providers",
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "providers",
        sa.Column(
            "visibility",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'public'"),
        ),
    )
    op.create_index(
        "ix_providers_owner_id",
        "providers",
        ["owner_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_providers_owner_id_users",
        "providers",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Table for user-submitted providers awaiting review.
    op.create_table(
        "provider_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=16), nullable=False, server_default=sa.text("'native'")),
        sa.Column("encrypted_config", sa.Text(), nullable=True),
        sa.Column("encrypted_api_key", sa.LargeBinary(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(("user_id",), ("users.id",), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(("reviewed_by",), ("users.id",), ondelete="SET NULL"),
    )
    op.create_index(
        "ix_provider_submissions_user_id",
        "provider_submissions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_submissions_reviewed_by",
        "provider_submissions",
        ["reviewed_by"],
        unique=False,
    )

    # Table for per-user permissions and quotas.
    op.create_table(
        "user_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_type", sa.String(length=32), nullable=False),
        sa.Column("permission_value", sa.String(length=100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(("user_id",), ("users.id",), ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id",
            "permission_type",
            name="uq_user_permissions_user_permission_type",
        ),
    )
    op.create_index(
        "ix_user_permissions_user_id",
        "user_permissions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_permissions_user_id", table_name="user_permissions")
    op.drop_table("user_permissions")

    op.drop_index("ix_provider_submissions_reviewed_by", table_name="provider_submissions")
    op.drop_index("ix_provider_submissions_user_id", table_name="provider_submissions")
    op.drop_table("provider_submissions")

    op.drop_constraint("fk_providers_owner_id_users", "providers", type_="foreignkey")
    op.drop_index("ix_providers_owner_id", table_name="providers")
    op.drop_column("providers", "visibility")
    op.drop_column("providers", "owner_id")
