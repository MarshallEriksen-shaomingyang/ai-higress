"""Partition provider_routing_metrics_history by day (Postgres only).

Motivation:
- The minute-bucket metrics history table grows quickly.
- Daily range partitioning enables fast retention via DROP PARTITION
  instead of large DELETEs (reduces bloat and lock impact).

Strategy:
- Rename the existing table to *_old (and rename its constraints/indexes to avoid name conflicts).
- Create a new partitioned table with the original name.
- Create daily partitions to cover existing data range (+ a small future buffer).
- Add the existing uniqueness constraint (required by ON CONFLICT upserts).
- Copy data back from the old table.

Notes:
- This migration is Postgres-only; on other dialects it is a no-op.
- We intentionally keep the old table as provider_routing_metrics_history__old for safety.
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa

from alembic import op

revision = "0040_partition_provider_routing_metrics_history_by_day"
down_revision = "0039_add_composite_indexes_for_metrics_history"
branch_labels = None
depends_on = None


def _utc_today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _iter_days(start: dt.date, end_exclusive: dt.date):
    cur = start
    while cur < end_exclusive:
        yield cur
        cur = cur + dt.timedelta(days=1)


def _partition_name(day: dt.date) -> str:
    return f"provider_routing_metrics_history_p{day.strftime('%Y%m%d')}"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Determine existing data range (if any) so we can create partitions that cover it.
    min_max = bind.execute(
        sa.text(
            "SELECT min(window_start) AS min_ts, max(window_start) AS max_ts "
            "FROM provider_routing_metrics_history"
        )
    ).one()
    min_ts = min_max[0]
    max_ts = min_max[1]

    today = _utc_today()
    if min_ts is None or max_ts is None:
        start_day = today - dt.timedelta(days=30)
        end_day = today + dt.timedelta(days=3)
    else:
        # Cover the whole historical range plus a small future buffer.
        start_day = min_ts.astimezone(dt.UTC).date()
        end_day = (max_ts.astimezone(dt.UTC).date() + dt.timedelta(days=1))
        end_day = max(end_day, today + dt.timedelta(days=3))

    # 1) Rename old table out of the way and rename its constraint/index names to avoid collisions.
    op.execute("ALTER TABLE provider_routing_metrics_history RENAME TO provider_routing_metrics_history__old")

    # Constraints (best-effort; Postgres does not support RENAME CONSTRAINT IF EXISTS).
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_provider_routing_metrics_history_bucket') THEN
            EXECUTE 'ALTER TABLE provider_routing_metrics_history__old '
                    'RENAME CONSTRAINT uq_provider_routing_metrics_history_bucket '
                    'TO uq_provider_routing_metrics_history_bucket__old';
          END IF;
          IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'provider_routing_metrics_history_pkey') THEN
            EXECUTE 'ALTER TABLE provider_routing_metrics_history__old '
                    'RENAME CONSTRAINT provider_routing_metrics_history_pkey '
                    'TO provider_routing_metrics_history__old_pkey';
          END IF;
        END $$;
        """
    )

    # Indexes (best-effort).
    index_names = [
        "ix_provider_routing_metrics_history_provider_id",
        "ix_provider_routing_metrics_history_logical_model",
        "ix_provider_routing_metrics_history_window_start",
        "ix_provider_routing_metrics_history_provider_logical_window",
        "ix_provider_routing_metrics_history_user_id",
        "ix_provider_routing_metrics_history_api_key_id",
        "ix_provider_routing_metrics_history_user_window",
        "ix_provider_routing_metrics_history_api_key_window",
        # The PK creates a backing index with the same name as the constraint by default.
        "provider_routing_metrics_history_pkey",
    ]
    for name in index_names:
        op.execute(f"ALTER INDEX IF EXISTS {name} RENAME TO {name}__old")

    # 2) Create the new partitioned table (same schema, but no primary key constraint on parent).
    op.execute(
        """
        CREATE TABLE provider_routing_metrics_history (
            id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            provider_id varchar(50) NOT NULL,
            logical_model varchar(100) NOT NULL,
            transport varchar(16) NOT NULL DEFAULT 'http',
            is_stream boolean NOT NULL DEFAULT FALSE,
            user_id uuid NULL,
            api_key_id uuid NULL,
            window_start timestamptz NOT NULL,
            window_duration integer NOT NULL DEFAULT 60,
            total_requests_1m integer NOT NULL,
            success_requests integer NOT NULL DEFAULT 0,
            error_requests integer NOT NULL DEFAULT 0,
            latency_avg_ms double precision NOT NULL DEFAULT 0,
            latency_p50_ms double precision NOT NULL DEFAULT 0,
            latency_p95_ms double precision NOT NULL,
            latency_p99_ms double precision NOT NULL,
            error_rate double precision NOT NULL,
            success_qps_1m double precision NOT NULL,
            status varchar(16) NOT NULL,
            error_4xx_requests integer NOT NULL DEFAULT 0,
            error_5xx_requests integer NOT NULL DEFAULT 0,
            error_429_requests integer NOT NULL DEFAULT 0,
            error_timeout_requests integer NOT NULL DEFAULT 0,
            input_tokens_sum integer NOT NULL DEFAULT 0,
            output_tokens_sum integer NOT NULL DEFAULT 0,
            total_tokens_sum integer NOT NULL DEFAULT 0,
            token_estimated_requests integer NOT NULL DEFAULT 0
        ) PARTITION BY RANGE (window_start);
        """
    )

    # Default partition: catch any out-of-range inserts (should be rare; tasks will pre-create partitions).
    op.execute(
        "CREATE TABLE provider_routing_metrics_history_default "
        "PARTITION OF provider_routing_metrics_history DEFAULT"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS provider_routing_metrics_history_default_provider_logical_window "
        "ON provider_routing_metrics_history_default (provider_id, logical_model, transport, is_stream, window_start)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS provider_routing_metrics_history_default_user_window "
        "ON provider_routing_metrics_history_default (user_id, window_start)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS provider_routing_metrics_history_default_api_key_window "
        "ON provider_routing_metrics_history_default (api_key_id, window_start)"
    )

    # 3) Create day partitions.
    for day in _iter_days(start_day, end_day):
        part = _partition_name(day)
        start = dt.datetime.combine(day, dt.time(0, 0, 0), tzinfo=dt.UTC).isoformat()
        end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 0, 0), tzinfo=dt.UTC).isoformat()
        op.execute(
            f"CREATE TABLE IF NOT EXISTS {part} "
            f"PARTITION OF provider_routing_metrics_history "
            f"FOR VALUES FROM ('{start}') TO ('{end}')"
        )

        # Local indexes (per-partition) for common dashboard query patterns.
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {part}_provider_logical_window "
            f"ON {part} (provider_id, logical_model, transport, is_stream, window_start)"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {part}_user_window "
            f"ON {part} (user_id, window_start)"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {part}_api_key_window "
            f"ON {part} (api_key_id, window_start)"
        )

    # 4) Add the uniqueness constraint used by UPSERT logic.
    op.execute(
        """
        ALTER TABLE provider_routing_metrics_history
        ADD CONSTRAINT uq_provider_routing_metrics_history_bucket
        UNIQUE (
            provider_id,
            logical_model,
            transport,
            is_stream,
            user_id,
            api_key_id,
            window_start
        );
        """
    )

    # 5) Copy existing data back.
    op.execute(
        """
        INSERT INTO provider_routing_metrics_history (
            id,
            created_at,
            updated_at,
            provider_id,
            logical_model,
            transport,
            is_stream,
            user_id,
            api_key_id,
            window_start,
            window_duration,
            total_requests_1m,
            success_requests,
            error_requests,
            latency_avg_ms,
            latency_p50_ms,
            latency_p95_ms,
            latency_p99_ms,
            error_rate,
            success_qps_1m,
            status,
            error_4xx_requests,
            error_5xx_requests,
            error_429_requests,
            error_timeout_requests,
            input_tokens_sum,
            output_tokens_sum,
            total_tokens_sum,
            token_estimated_requests
        )
        SELECT
            id,
            created_at,
            updated_at,
            provider_id,
            logical_model,
            transport,
            is_stream,
            user_id,
            api_key_id,
            window_start,
            window_duration,
            total_requests_1m,
            success_requests,
            error_requests,
            latency_avg_ms,
            latency_p50_ms,
            latency_p95_ms,
            latency_p99_ms,
            error_rate,
            success_qps_1m,
            status,
            error_4xx_requests,
            error_5xx_requests,
            error_429_requests,
            error_timeout_requests,
            input_tokens_sum,
            output_tokens_sum,
            total_tokens_sum,
            token_estimated_requests
        FROM provider_routing_metrics_history__old;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Best-effort rollback: drop partitioned table (incl. partitions) and restore the old table name.
    op.execute("DROP TABLE IF EXISTS provider_routing_metrics_history CASCADE")
    op.execute("ALTER TABLE provider_routing_metrics_history__old RENAME TO provider_routing_metrics_history")

    # Attempt to restore original names (best-effort).
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_provider_routing_metrics_history_bucket__old') THEN
            EXECUTE 'ALTER TABLE provider_routing_metrics_history '
                    'RENAME CONSTRAINT uq_provider_routing_metrics_history_bucket__old '
                    'TO uq_provider_routing_metrics_history_bucket';
          END IF;
          IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'provider_routing_metrics_history__old_pkey') THEN
            EXECUTE 'ALTER TABLE provider_routing_metrics_history '
                    'RENAME CONSTRAINT provider_routing_metrics_history__old_pkey '
                    'TO provider_routing_metrics_history_pkey';
          END IF;
        END $$;
        """
    )
