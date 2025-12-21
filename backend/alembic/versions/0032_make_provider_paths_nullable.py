"""Make provider API paths nullable

Revision ID: 0032_make_provider_paths_nullable
Revises: 0031_add_upstream_proxy_management
Create Date: 2025-12-13

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0032_make_provider_paths_nullable"
down_revision = "0031_add_upstream_proxy_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    将 providers 和 provider_presets 表的 models_path 和 chat_completions_path 字段改为可空，
    允许用户根据实际 API 情况灵活配置路径。
    """
    # 修改 providers 表
    op.alter_column(
        "providers",
        "models_path",
        existing_type=sa.String(length=100),
        nullable=True,
        existing_server_default=sa.text("'/v1/models'"),
    )

    op.alter_column(
        "providers",
        "chat_completions_path",
        existing_type=sa.String(length=100),
        nullable=True,
        existing_server_default=sa.text("'/v1/chat/completions'"),
    )

    # 修改 provider_presets 表
    op.alter_column(
        "provider_presets",
        "models_path",
        existing_type=sa.String(length=100),
        nullable=True,
        existing_server_default=sa.text("'/v1/models'"),
    )

    op.alter_column(
        "provider_presets",
        "chat_completions_path",
        existing_type=sa.String(length=100),
        nullable=True,
        existing_server_default=sa.text("'/v1/chat/completions'"),
    )


def downgrade() -> None:
    """
    回滚：将字段改回不可空，并设置默认值
    """
    # 先将 NULL 值更新为默认值
    op.execute(
        "UPDATE providers SET models_path = '/v1/models' WHERE models_path IS NULL"
    )
    op.execute(
        "UPDATE providers SET chat_completions_path = '/v1/chat/completions' WHERE chat_completions_path IS NULL"
    )
    op.execute(
        "UPDATE provider_presets SET models_path = '/v1/models' WHERE models_path IS NULL"
    )
    op.execute(
        "UPDATE provider_presets SET chat_completions_path = '/v1/chat/completions' WHERE chat_completions_path IS NULL"
    )

    # 修改 providers 表
    op.alter_column(
        "providers",
        "models_path",
        existing_type=sa.String(length=100),
        nullable=False,
        existing_server_default=sa.text("'/v1/models'"),
    )

    op.alter_column(
        "providers",
        "chat_completions_path",
        existing_type=sa.String(length=100),
        nullable=False,
        existing_server_default=sa.text("'/v1/chat/completions'"),
    )

    # 修改 provider_presets 表
    op.alter_column(
        "provider_presets",
        "models_path",
        existing_type=sa.String(length=100),
        nullable=False,
        existing_server_default=sa.text("'/v1/models'"),
    )

    op.alter_column(
        "provider_presets",
        "chat_completions_path",
        existing_type=sa.String(length=100),
        nullable=False,
        existing_server_default=sa.text("'/v1/chat/completions'"),
    )
