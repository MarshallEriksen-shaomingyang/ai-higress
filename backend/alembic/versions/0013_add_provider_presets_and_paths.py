"""Add provider presets table and provider path metadata"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_add_provider_presets_and_paths"
down_revision = "0012_add_roles_and_seed_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("preset_id", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider_type", sa.String(length=16), nullable=False, server_default=sa.text("'native'")),
        sa.Column("transport", sa.String(length=16), nullable=False, server_default=sa.text("'http'")),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("models_path", sa.String(length=100), nullable=False, server_default=sa.text("'/v1/models'")),
        sa.Column("messages_path", sa.String(length=100), nullable=True),
        sa.Column("chat_completions_path", sa.String(length=100), nullable=False, server_default=sa.text("'/v1/chat/completions'")),
        sa.Column("responses_path", sa.String(length=100), nullable=True),
        sa.Column("supported_api_styles", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retryable_status_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("custom_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("static_models", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.UniqueConstraint("preset_id", name="uq_provider_presets_preset_id"),
    )
    op.create_index(
        "ix_provider_presets_preset_id",
        "provider_presets",
        ["preset_id"],
        unique=False,
    )

    op.add_column(
        "providers",
        sa.Column("chat_completions_path", sa.String(length=100), nullable=False, server_default=sa.text("'/v1/chat/completions'")),
    )
    op.add_column(
        "providers",
        sa.Column("responses_path", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "providers",
        sa.Column(
            "supported_api_styles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "providers",
        sa.Column("preset_uuid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_providers_preset_uuid", "providers", ["preset_uuid"], unique=False)
    op.create_foreign_key(
        "fk_providers_preset_uuid_provider_presets",
        "providers",
        "provider_presets",
        ["preset_uuid"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_providers_preset_uuid_provider_presets", table_name="providers"
    )
    op.drop_index("ix_providers_preset_uuid", table_name="providers")
    op.drop_column("providers", "preset_uuid")
    op.drop_column("providers", "supported_api_styles")
    op.drop_column("providers", "responses_path")
    op.drop_column("providers", "chat_completions_path")

    op.drop_index("ix_provider_presets_preset_id", table_name="provider_presets")
    op.drop_table("provider_presets")
