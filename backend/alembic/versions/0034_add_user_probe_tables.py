"""Add user probe tasks and runs tables.

Revision ID: 0034_add_user_probe_tables
Revises: 0033_add_claude_cli_transport_type
Create Date: 2025-12-15

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0034_add_user_probe_tables"
down_revision = "0033_add_claude_cli_transport_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_probe_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default=sa.text("16")),
        sa.Column("api_style", sa.String(length=16), nullable=False, server_default=sa.text("'auto'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("in_progress", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_probe_tasks_user_id", "user_probe_tasks", ["user_id"])
    op.create_index("ix_user_probe_tasks_provider_uuid", "user_probe_tasks", ["provider_uuid"])
    op.create_index("ix_user_probe_tasks_next_run_at", "user_probe_tasks", ["next_run_at"])

    op.create_table(
        "user_probe_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column(
            "task_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_probe_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("api_style", sa.String(length=16), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_excerpt", sa.Text(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_probe_runs_task_uuid", "user_probe_runs", ["task_uuid"])
    op.create_index("ix_user_probe_runs_user_id", "user_probe_runs", ["user_id"])
    op.create_index("ix_user_probe_runs_provider_uuid", "user_probe_runs", ["provider_uuid"])

    op.add_column(
        "user_probe_tasks",
        sa.Column(
            "last_run_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_probe_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_probe_tasks", "last_run_uuid")

    op.drop_index("ix_user_probe_runs_provider_uuid", table_name="user_probe_runs")
    op.drop_index("ix_user_probe_runs_user_id", table_name="user_probe_runs")
    op.drop_index("ix_user_probe_runs_task_uuid", table_name="user_probe_runs")
    op.drop_table("user_probe_runs")

    op.drop_index("ix_user_probe_tasks_next_run_at", table_name="user_probe_tasks")
    op.drop_index("ix_user_probe_tasks_provider_uuid", table_name="user_probe_tasks")
    op.drop_index("ix_user_probe_tasks_user_id", table_name="user_probe_tasks")
    op.drop_table("user_probe_tasks")
