"""Add role tables and seed initial permissions."""
from __future__ import annotations

from datetime import UTC

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_add_roles_and_seed_permissions"
down_revision = "0011_add_user_and_api_key_to_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 角色相关表 ----
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(("role_id",), ("roles.id",), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(("permission_id",), ("permissions.id",), ondelete="CASCADE"),
        sa.UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permissions_role_permission",
        ),
    )
    op.create_index(
        "ix_role_permissions_role_id",
        "role_permissions",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_permissions_permission_id",
        "role_permissions",
        ["permission_id"],
        unique=False,
    )

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(("role_id",), ("roles.id",), ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id",
            "role_id",
            name="uq_user_roles_user_role",
        ),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"], unique=False)
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"], unique=False)

    # ---- 预填充权限定义 ----
    permissions_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String(length=100)),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    # 这里只填充代码中已经使用到的权限以及一些常见的管理权限，方便后续基于角色分配
    initial_permissions = [
        # 已在 UserPermission 中使用的权限
        ("create_private_provider", "允许创建私有 Provider"),
        ("submit_shared_provider", "允许提交共享 Provider 进行审核"),
        ("unlimited_providers", "私有 Provider 数量无限制"),
        ("private_provider_limit", "自定义用户私有 Provider 数量上限"),
        # 用户与权限管理
        ("manage_users", "管理用户（创建/更新/删除等）"),
        ("manage_user_status", "更新用户状态（封禁/解封）"),
        ("manage_user_permissions", "为用户授予或撤销细粒度权限"),
        # API Key 管理
        ("manage_own_api_keys", "管理自己的 API Key"),
        ("manage_all_api_keys", "管理所有用户的 API Key"),
        ("manage_api_key_provider_restrictions", "管理 API Key 的可访问 Provider 列表"),
        # Provider 管理
        ("admin_view_providers", "查看所有 Provider 列表和详情"),
        ("admin_update_provider_visibility", "更新 Provider 的可见性"),
        ("manage_provider_keys", "管理上游厂商 API 密钥"),
        # Provider 提交与审核
        ("review_shared_provider", "审核共享 Provider 提交"),
        ("view_provider_submissions", "查看 Provider 提交列表"),
        # 系统配置
        ("generate_system_secret_key", "生成系统主密钥"),
        ("rotate_system_secret_key", "轮换系统主密钥"),
        ("view_system_status", "查看系统运行状态"),
        ("view_provider_limits", "查看系统 Provider 配额配置"),
        ("update_provider_limits", "更新系统 Provider 配额配置"),
        # 监控与路由
        ("view_provider_metrics", "查看 Provider 路由指标"),
        ("view_provider_health", "查看 Provider 健康状态"),
        ("view_routing_decisions", "查看路由决策及候选上游"),
    ]

    from datetime import datetime
    from uuid import uuid4

    now = datetime.now(UTC)

    rows = [
        {
            "id": uuid4(),
            "code": code,
            "description": desc,
            "created_at": now,
            "updated_at": now,
        }
        for code, desc in initial_permissions
    ]

    # 使用 ON CONFLICT 语义避免重复插入（针对已有环境可能已手动写入部分权限）
    conn = op.get_bind()
    for row in rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, description, created_at, updated_at)
                VALUES (:id, :code, :description, :created_at, :updated_at)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            row,
        )


def downgrade() -> None:
    # 回滚角色相关表
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_table("role_permissions")

    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")

    # 不删除 permissions 中已插入的数据，以免误删线上已有配置

