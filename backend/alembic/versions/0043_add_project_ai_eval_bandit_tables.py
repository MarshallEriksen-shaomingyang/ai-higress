"""Add project AI recommend-eval and bandit tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0043_add_project_ai_eval_bandit_tables"
down_revision = "0042_create_user_app_request_metrics_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_eval_configs",
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
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "max_challengers",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("2"),
        ),
        sa.Column(
            "provider_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"private\",\"shared\",\"public\"]'"),
        ),
        sa.Column(
            "candidate_logical_models",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("budget_per_eval_credits", sa.Integer(), nullable=True),
        sa.Column("rubric", sa.Text(), nullable=True),
        sa.Column("project_ai_provider_model", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_project_eval_configs_api_key_id",
        "project_eval_configs",
        ["api_key_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_project_eval_configs_api_key_id",
        "project_eval_configs",
        ["api_key_id"],
    )

    op.create_table(
        "assistant_presets",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("default_logical_model", sa.String(length=128), nullable=False),
        sa.Column("model_preset", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_assistant_presets_user_id", "assistant_presets", ["user_id"], unique=False)
    op.create_index("ix_assistant_presets_api_key_id", "assistant_presets", ["api_key_id"], unique=False)
    op.create_unique_constraint(
        "uq_assistant_presets_user_project_name",
        "assistant_presets",
        ["user_id", "api_key_id", "name"],
    )

    op.create_table(
        "chat_conversations",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistant_presets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"], unique=False)
    op.create_index("ix_chat_conversations_api_key_id", "chat_conversations", ["api_key_id"], unique=False)
    op.create_index("ix_chat_conversations_assistant_id", "chat_conversations", ["assistant_id"], unique=False)
    op.create_index(
        "ix_chat_conversations_user_assistant_last_activity",
        "chat_conversations",
        ["user_id", "assistant_id", "last_activity_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
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
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chat_messages_conversation_id",
        "chat_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_chat_messages_conversation_sequence",
        "chat_messages",
        ["conversation_id", "sequence"],
    )

    op.create_table(
        "chat_runs",
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
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_logical_model", sa.String(length=128), nullable=False),
        sa.Column("selected_provider_id", sa.String(length=64), nullable=True),
        sa.Column("selected_provider_model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_credits", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("output_preview", sa.String(length=400), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_runs_message_id", "chat_runs", ["message_id"], unique=False)
    op.create_index("ix_chat_runs_user_id", "chat_runs", ["user_id"], unique=False)
    op.create_index("ix_chat_runs_api_key_id", "chat_runs", ["api_key_id"], unique=False)
    op.create_index("ix_chat_runs_message_created", "chat_runs", ["message_id", "created_at"], unique=False)
    op.create_index("ix_chat_runs_user_created", "chat_runs", ["user_id", "created_at"], unique=False)

    op.create_table(
        "chat_evals",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("baseline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "challenger_run_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "effective_provider_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("context_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=False, server_default=sa.text("'ts-v1'")),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'running'")),
        sa.Column("rated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistant_presets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["chat_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_evals_user_id", "chat_evals", ["user_id"], unique=False)
    op.create_index("ix_chat_evals_api_key_id", "chat_evals", ["api_key_id"], unique=False)
    op.create_index("ix_chat_evals_baseline_run_id", "chat_evals", ["baseline_run_id"], unique=False)
    op.create_unique_constraint("uq_chat_evals_baseline_run_id", "chat_evals", ["baseline_run_id"])

    op.create_table(
        "chat_eval_ratings",
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
        sa.Column("eval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("winner_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reason_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.ForeignKeyConstraint(["eval_id"], ["chat_evals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_run_id"], ["chat_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_eval_ratings_eval_id", "chat_eval_ratings", ["eval_id"], unique=False)
    op.create_index("ix_chat_eval_ratings_user_id", "chat_eval_ratings", ["user_id"], unique=False)
    op.create_unique_constraint(
        "uq_chat_eval_ratings_eval_user",
        "chat_eval_ratings",
        ["eval_id", "user_id"],
    )

    op.create_table(
        "bandit_arm_stats",
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
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_key", sa.String(length=64), nullable=False),
        sa.Column("arm_logical_model", sa.String(length=128), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("beta", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("wins", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("losses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistant_presets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_bandit_arm_stats_api_key_id", "bandit_arm_stats", ["api_key_id"], unique=False)
    op.create_index("ix_bandit_arm_stats_assistant_id", "bandit_arm_stats", ["assistant_id"], unique=False)
    op.create_index("ix_bandit_arm_stats_context_key", "bandit_arm_stats", ["context_key"], unique=False)
    op.create_index("ix_bandit_arm_stats_arm_logical_model", "bandit_arm_stats", ["arm_logical_model"], unique=False)
    op.create_unique_constraint(
        "uq_bandit_arm_stats_project_context_arm",
        "bandit_arm_stats",
        ["api_key_id", "context_key", "arm_logical_model"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_bandit_arm_stats_project_context_arm",
        "bandit_arm_stats",
        type_="unique",
    )
    op.drop_index("ix_bandit_arm_stats_arm_logical_model", table_name="bandit_arm_stats")
    op.drop_index("ix_bandit_arm_stats_context_key", table_name="bandit_arm_stats")
    op.drop_index("ix_bandit_arm_stats_assistant_id", table_name="bandit_arm_stats")
    op.drop_index("ix_bandit_arm_stats_api_key_id", table_name="bandit_arm_stats")
    op.drop_table("bandit_arm_stats")

    op.drop_constraint(
        "uq_chat_eval_ratings_eval_user",
        "chat_eval_ratings",
        type_="unique",
    )
    op.drop_index("ix_chat_eval_ratings_user_id", table_name="chat_eval_ratings")
    op.drop_index("ix_chat_eval_ratings_eval_id", table_name="chat_eval_ratings")
    op.drop_table("chat_eval_ratings")

    op.drop_constraint("uq_chat_evals_baseline_run_id", "chat_evals", type_="unique")
    op.drop_index("ix_chat_evals_baseline_run_id", table_name="chat_evals")
    op.drop_index("ix_chat_evals_api_key_id", table_name="chat_evals")
    op.drop_index("ix_chat_evals_user_id", table_name="chat_evals")
    op.drop_table("chat_evals")

    op.drop_index("ix_chat_runs_user_created", table_name="chat_runs")
    op.drop_index("ix_chat_runs_message_created", table_name="chat_runs")
    op.drop_index("ix_chat_runs_api_key_id", table_name="chat_runs")
    op.drop_index("ix_chat_runs_user_id", table_name="chat_runs")
    op.drop_index("ix_chat_runs_message_id", table_name="chat_runs")
    op.drop_table("chat_runs")

    op.drop_constraint(
        "uq_chat_messages_conversation_sequence",
        "chat_messages",
        type_="unique",
    )
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_conversations_user_assistant_last_activity", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_assistant_id", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_api_key_id", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_user_id", table_name="chat_conversations")
    op.drop_table("chat_conversations")

    op.drop_constraint(
        "uq_assistant_presets_user_project_name",
        "assistant_presets",
        type_="unique",
    )
    op.drop_index("ix_assistant_presets_api_key_id", table_name="assistant_presets")
    op.drop_index("ix_assistant_presets_user_id", table_name="assistant_presets")
    op.drop_table("assistant_presets")

    op.drop_constraint(
        "uq_project_eval_configs_api_key_id",
        "project_eval_configs",
        type_="unique",
    )
    op.drop_index("ix_project_eval_configs_api_key_id", table_name="project_eval_configs")
    op.drop_table("project_eval_configs")
