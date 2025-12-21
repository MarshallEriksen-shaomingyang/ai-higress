"""Add provider tables."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_add_provider_tables"
down_revision = "0003_add_api_keys_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("transport", sa.String(length=16), nullable=False, server_default=sa.text("'http'")),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("cost_input", sa.Float(), nullable=True),
        sa.Column("cost_output", sa.Float(), nullable=True),
        sa.Column("max_qps", sa.Integer(), nullable=True),
        sa.Column(
            "retryable_status_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("custom_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("models_path", sa.String(length=100), nullable=False, server_default=sa.text("'/v1/models'")),
        sa.Column("messages_path", sa.String(length=100), nullable=True),
        sa.Column("static_models", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'healthy'")),
        sa.Column("last_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.UniqueConstraint("provider_id", name="uq_providers_provider_id"),
    )

    op.create_table(
        "provider_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("max_qps", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
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
        sa.ForeignKeyConstraint(("provider_uuid",), ("providers.id",), ondelete="CASCADE"),
    )
    op.create_index(
        "ix_provider_api_keys_provider_uuid",
        "provider_api_keys",
        ["provider_uuid"],
        unique=False,
    )

    op.create_table(
        "provider_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("family", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pricing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("meta_hash", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(("provider_id",), ("providers.id",), ondelete="CASCADE"),
        sa.UniqueConstraint("provider_id", "model_id", name="uq_provider_models_provider_model"),
    )
    op.create_index(
        "ix_provider_models_provider_id",
        "provider_models",
        ["provider_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_models_provider_id", table_name="provider_models")
    op.drop_table("provider_models")
    op.drop_index("ix_provider_api_keys_provider_uuid", table_name="provider_api_keys")
    op.drop_table("provider_api_keys")
    op.drop_table("providers")
