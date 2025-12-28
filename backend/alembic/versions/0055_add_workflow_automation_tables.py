"""Add workflow automation tables.

Revision ID: 0055_add_workflow_automation_tables
Revises: 0054_add_conversation_summary_fields
Create Date: 2025-12-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055_add_workflow_automation_tables"
down_revision = "0054_add_conversation_summary_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spec_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_workflows_user_created", "workflows", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_workflows_user_id"), "workflows", ["user_id"], unique=False)

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("workflow_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'paused'"), nullable=False),
        sa.Column("paused_reason", sa.String(length=64), nullable=True),
        sa.Column("current_step_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("workflow_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("steps_state", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
    )
    op.create_index("ix_workflow_runs_user_created", "workflow_runs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_workflow_runs_workflow_created", "workflow_runs", ["workflow_id", "created_at"], unique=False)
    op.create_index("ix_workflow_runs_status_updated", "workflow_runs", ["status", "updated_at"], unique=False)
    op.create_index(op.f("ix_workflow_runs_workflow_id"), "workflow_runs", ["workflow_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_user_id"), "workflow_runs", ["user_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_last_activity_at"), "workflow_runs", ["last_activity_at"], unique=False)

    op.create_table(
        "workflow_run_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.UniqueConstraint("run_id", "seq", name="uq_workflow_run_events_run_seq"),
    )
    op.create_index("ix_workflow_run_events_run_created", "workflow_run_events", ["run_id", "created_at"], unique=False)
    op.create_index(op.f("ix_workflow_run_events_run_id"), "workflow_run_events", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_run_events_run_id"), table_name="workflow_run_events")
    op.drop_index("ix_workflow_run_events_run_created", table_name="workflow_run_events")
    op.drop_table("workflow_run_events")

    op.drop_index(op.f("ix_workflow_runs_last_activity_at"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_user_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_workflow_id"), table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_status_updated", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_created", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_user_created", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index(op.f("ix_workflows_user_id"), table_name="workflows")
    op.drop_index("ix_workflows_user_created", table_name="workflows")
    op.drop_table("workflows")
