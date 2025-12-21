"""Add alias field to provider_models for per-model mapping."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# 注意：此迁移最初是基于 0010 创建的，为避免产生多个 head，
# 这里将 revision 调整为在现有链路之后的 0022，并依赖最新的 0021。
revision = "0022_add_provider_model_alias"
down_revision = "0021_add_credit_auto_topup_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_models",
        sa.Column("alias", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_models", "alias")

