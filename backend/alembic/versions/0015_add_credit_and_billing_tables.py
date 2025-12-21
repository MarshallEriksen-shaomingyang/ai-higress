"""Add credit accounts, transactions and model billing config tables"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0015_add_credit_and_billing_tables"
down_revision = "0014_add_sdk_vendor_to_providers_and_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 用户积分账户
    op.create_table(
        "credit_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "balance",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
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
        sa.UniqueConstraint("user_id", name="uq_credit_accounts_user_id"),
    )
    op.create_index(
        "ix_credit_accounts_user_id",
        "credit_accounts",
        ["user_id"],
        unique=False,
    )

    # 积分流水
    op.create_table(
        "credit_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "reason",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'usage'"),
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ("account_id",),
            ("credit_accounts.id",),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ("user_id",),
            ("users.id",),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ("api_key_id",),
            ("api_keys.id",),
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_credit_transactions_account_id",
        "credit_transactions",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_credit_transactions_user_id",
        "credit_transactions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_credit_transactions_api_key_id",
        "credit_transactions",
        ["api_key_id"],
        unique=False,
    )

    # 模型计费配置
    op.create_table(
        "model_billing_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column(
            "multiplier",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
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
        sa.UniqueConstraint(
            "model_name",
            name="uq_model_billing_configs_model_name",
        ),
    )
    op.create_index(
        "ix_model_billing_configs_model_name",
        "model_billing_configs",
        ["model_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_billing_configs_model_name",
        table_name="model_billing_configs",
    )
    op.drop_table("model_billing_configs")

    op.drop_index(
        "ix_credit_transactions_api_key_id",
        table_name="credit_transactions",
    )
    op.drop_index(
        "ix_credit_transactions_user_id",
        table_name="credit_transactions",
    )
    op.drop_index(
        "ix_credit_transactions_account_id",
        table_name="credit_transactions",
    )
    op.drop_table("credit_transactions")

    op.drop_index(
        "ix_credit_accounts_user_id",
        table_name="credit_accounts",
    )
    op.drop_table("credit_accounts")

