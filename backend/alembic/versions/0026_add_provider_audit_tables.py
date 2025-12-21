"""Add provider audit/test tables and statuses."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0026_add_provider_audit_tables"
down_revision = "0025_add_provider_allowed_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column(
            "audit_status",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column(
        "providers",
        sa.Column(
            "operation_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )

    op.create_table(
        "provider_test_records",
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
            "provider_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'auto'"),
        ),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("probe_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_provider_test_records_provider_uuid",
        "provider_test_records",
        ["provider_uuid"],
    )

    op.create_table(
        "provider_audit_logs",
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
            "provider_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("operation_from_status", sa.String(length=16), nullable=True),
        sa.Column("operation_to_status", sa.String(length=16), nullable=True),
        sa.Column(
            "operator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "test_record_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_test_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_provider_audit_logs_provider_uuid",
        "provider_audit_logs",
        ["provider_uuid"],
    )
    op.create_index(
        "ix_provider_audit_logs_operator_id",
        "provider_audit_logs",
        ["operator_id"],
    )
    op.create_index(
        "ix_provider_audit_logs_test_record_uuid",
        "provider_audit_logs",
        ["test_record_uuid"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_audit_logs_test_record_uuid", table_name="provider_audit_logs")
    op.drop_index("ix_provider_audit_logs_operator_id", table_name="provider_audit_logs")
    op.drop_index("ix_provider_audit_logs_provider_uuid", table_name="provider_audit_logs")
    op.drop_table("provider_audit_logs")

    op.drop_index("ix_provider_test_records_provider_uuid", table_name="provider_test_records")
    op.drop_table("provider_test_records")

    op.drop_column("providers", "operation_status")
    op.drop_column("providers", "audit_status")
