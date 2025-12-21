"""Add eval_id to chat_runs for fast eval status updates."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0045_add_eval_id_to_chat_runs"
down_revision = "0044_add_project_ai_enabled_to_project_eval_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_runs",
        sa.Column("eval_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_chat_runs_eval_id", "chat_runs", ["eval_id"], unique=False)
    op.create_foreign_key(
        "fk_chat_runs_eval_id",
        "chat_runs",
        "chat_evals",
        ["eval_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_runs_eval_id", "chat_runs", type_="foreignkey")
    op.drop_index("ix_chat_runs_eval_id", table_name="chat_runs")
    op.drop_column("chat_runs", "eval_id")

