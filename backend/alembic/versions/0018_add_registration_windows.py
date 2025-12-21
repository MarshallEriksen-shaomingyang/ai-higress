import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018_add_registration_windows"
down_revision = "0017_add_approved_provider_to_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_enum = sa.Enum(
        "scheduled",
        "active",
        "closed",
        name="registrationwindowstatus",
    )

    # NOTE: we do not call status_enum.create() explicitly here.
    # Alembic/SQLAlchemy will create the underlying PostgreSQL enum
    # automatically when the table is created, and will use a
    # "check first" pattern to avoid duplicate CREATE TYPE calls.
    op.create_table(
        "registration_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_registrations", sa.Integer(), nullable=False),
        sa.Column(
            "registered_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "auto_activate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="scheduled",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_registration_windows_status_start",
        "registration_windows",
        ["status", "start_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_registration_windows_status_start", table_name="registration_windows")
    op.drop_table("registration_windows")
    sa.Enum(name="registrationwindowstatus").drop(op.get_bind(), checkfirst=True)
