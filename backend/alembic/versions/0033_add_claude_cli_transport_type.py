"""Add claude_cli transport type to providers

Revision ID: 0033_add_claude_cli_transport_type
Revises: 0032_make_provider_paths_nullable
Create Date: 2025-12-15

"""
from __future__ import annotations

from alembic import op

revision = "0033_add_claude_cli_transport_type"
down_revision = "0032_make_provider_paths_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    为 providers 表的 transport 字段添加 CHECK 约束，
    支持 'http', 'sdk', 'claude_cli' 三种传输类型。
    """
    # 添加 CHECK 约束限制 transport 字段的值
    op.create_check_constraint(
        "providers_transport_check",
        "providers",
        "transport IN ('http', 'sdk', 'claude_cli')"
    )


def downgrade() -> None:
    """
    回滚：删除 CHECK 约束
    """
    op.drop_constraint(
        "providers_transport_check",
        "providers",
        type_="check"
    )
