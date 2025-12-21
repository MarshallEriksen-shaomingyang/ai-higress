"""Add project_ai_enabled flag to project eval configs."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0044_add_project_ai_enabled_to_project_eval_configs"
down_revision = "0043_add_project_ai_eval_bandit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_eval_configs",
        sa.Column(
            "project_ai_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_eval_configs", "project_ai_enabled")

