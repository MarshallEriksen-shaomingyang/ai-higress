"""Add user risk status fields.

Revision ID: 0056_add_user_risk_fields
Revises: 0055_add_workflow_automation_tables
Create Date: 2025-12-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0056_add_user_risk_fields"
down_revision = "0055_add_workflow_automation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "risk_score",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "risk_level",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'low'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "risk_remark",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "risk_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_users_risk_level"), "users", ["risk_level"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_risk_level"), table_name="users")
    op.drop_column("users", "risk_updated_at")
    op.drop_column("users", "risk_remark")
    op.drop_column("users", "risk_level")
    op.drop_column("users", "risk_score")

