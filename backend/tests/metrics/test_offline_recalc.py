import datetime as dt

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.metrics.offline_recalc import OfflineMetricsRecalculator
from app.models import AggregateRoutingMetrics, Base, ProviderRoutingMetricsHistory


def _setup_session() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_history(
    session: Session,
    *,
    window_start: dt.datetime,
    total: int,
    success: int,
    error: int,
    latency_avg: float,
    latency_p95: float,
    latency_p99: float,
) -> None:
    session.add(
        ProviderRoutingMetricsHistory(
            provider_id="provider",
            logical_model="gpt-4",
            transport="http",
            is_stream=False,
            user_id=None,
            api_key_id=None,
            window_start=window_start,
            window_duration=60,
            total_requests_1m=total,
            success_requests=success,
            error_requests=error,
            latency_avg_ms=latency_avg,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            error_rate=error / total if total else 0.0,
            success_qps_1m=success / 60 if total else 0.0,
            status="healthy",
        )
    )
    session.commit()


def test_recalculate_and_persist_merges_window() -> None:
    SessionLocal = _setup_session()
    with SessionLocal() as session:
        # 固定一个时间点，避免基于当前时间导致的窗口对齐随机性（否则不同分钟会落到不同 5 分钟桶里，测试会变得不稳定）
        base = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        _seed_history(
            session,
            window_start=base - dt.timedelta(minutes=2),
            total=5,
            success=4,
            error=1,
            latency_avg=100.0,
            latency_p95=120.0,
            latency_p99=140.0,
        )
        _seed_history(
            session,
            window_start=base - dt.timedelta(minutes=3),
            total=5,
            success=4,
            error=1,
            latency_avg=200.0,
            latency_p95=220.0,
            latency_p99=260.0,
        )

        recalculator = OfflineMetricsRecalculator(
            diff_threshold=0.02, source_version="test", min_total_requests=1
        )
        written = recalculator.recalculate_and_persist(
            session,
            start=base - dt.timedelta(minutes=5),
            end=base + dt.timedelta(seconds=1),
            window_seconds=300,
        )
        session.commit()

        row = session.execute(select(AggregateRoutingMetrics)).scalar_one()
        assert written == 1
        assert row.total_requests == 10
        assert row.success_requests == 8
        assert row.error_requests == 2
        assert row.latency_p50_ms == 140.0
        assert row.latency_p90_ms == 220.0
        assert row.latency_p95_ms == 260.0
        assert row.latency_p99_ms == 260.0
        assert row.status == "degraded"


def test_recalculate_skips_when_no_diff() -> None:
    SessionLocal = _setup_session()
    with SessionLocal() as session:
        # 与上一个测试保持一致，使用固定的窗口基准时间，确保聚合窗口稳定
        base = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        _seed_history(
            session,
            window_start=base - dt.timedelta(minutes=2),
            total=4,
            success=4,
            error=0,
            latency_avg=80.0,
            latency_p95=100.0,
            latency_p99=120.0,
        )

        recalculator = OfflineMetricsRecalculator(
            diff_threshold=0.5, source_version="test", min_total_requests=1
        )
        first = recalculator.recalculate_and_persist(
            session,
            start=base - dt.timedelta(minutes=5),
            end=base + dt.timedelta(seconds=1),
            window_seconds=300,
        )
        session.commit()
        assert first == 1

        # 同样的数据不会触发二次写入
        second = recalculator.recalculate_and_persist(
            session,
            start=base - dt.timedelta(minutes=5),
            end=base + dt.timedelta(seconds=1),
            window_seconds=300,
        )
        assert second == 0

        # 新增高延迟样本，触发重新写回
        _seed_history(
            session,
            window_start=base - dt.timedelta(minutes=1),
            total=2,
            success=1,
            error=1,
            latency_avg=800.0,
            latency_p95=900.0,
            latency_p99=1000.0,
        )

        third = recalculator.recalculate_and_persist(
            session,
            start=base - dt.timedelta(minutes=5),
            end=base + dt.timedelta(seconds=1),
            window_seconds=300,
        )
        session.commit()
        assert third == 1
        refreshed = session.execute(select(AggregateRoutingMetrics)).scalar_one()
        assert refreshed.latency_p99_ms == 1000.0


def test_recalculate_and_persist_aligns_start_to_avoid_duplicate_bucket() -> None:
    SessionLocal = _setup_session()
    with SessionLocal() as session:
        start = dt.datetime(2024, 1, 1, 6, 11, tzinfo=dt.UTC)
        end = dt.datetime(2024, 1, 1, 7, 11, tzinfo=dt.UTC)

        _seed_history(
            session,
            window_start=start,
            total=2,
            success=2,
            error=0,
            latency_avg=100.0,
            latency_p95=150.0,
            latency_p99=200.0,
        )

        # 预先插入一个对齐到 06:00 的小时桶；若 recalc 用原始 start=06:11 查询 existing，
        # 会漏掉该记录并尝试重复插入，从而触发唯一约束冲突。
        session.add(
            AggregateRoutingMetrics(
                provider_id="provider",
                logical_model="gpt-4",
                transport="http",
                is_stream=False,
                user_id=None,
                api_key_id=None,
                window_start=dt.datetime(2024, 1, 1, 6, 0, tzinfo=dt.UTC),
                window_duration=3600,
                total_requests=0,
                success_requests=0,
                error_requests=0,
                latency_p50_ms=0.0,
                latency_p90_ms=0.0,
                latency_p95_ms=0.0,
                latency_p99_ms=0.0,
                error_rate=0.0,
                success_qps=0.0,
                status="unknown",
                recalculated_at=dt.datetime(2024, 1, 1, 6, 0, tzinfo=dt.UTC),
                source_version="seed",
            )
        )
        session.commit()

        recalculator = OfflineMetricsRecalculator(
            diff_threshold=0.0, source_version="test", min_total_requests=1
        )
        written = recalculator.recalculate_and_persist(
            session,
            start=start,
            end=end,
            window_seconds=3600,
        )
        session.commit()

        rows = session.execute(select(AggregateRoutingMetrics)).scalars().all()
        assert len(rows) == 1
        assert written == 1
        assert rows[0].window_start == dt.datetime(2024, 1, 1, 6, 0, tzinfo=dt.UTC)
        assert rows[0].total_requests == 2
