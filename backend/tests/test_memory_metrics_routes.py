from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import MemoryMetricsHourly, User
from tests.utils import jwt_auth_headers


def _fixed_now() -> dt.datetime:
    return dt.datetime(2026, 1, 2, 12, 0, 0, tzinfo=dt.timezone.utc)


def test_memory_kpis_hourly_derives_skipped_and_latency(app_with_inmemory_db, monkeypatch):
    app, SessionLocal = app_with_inmemory_db

    from app.api import memory_metrics_routes

    monkeypatch.setattr(memory_metrics_routes, "_utc_now", _fixed_now)

    with SessionLocal() as session:
        user_id = str(session.execute(select(User.id)).scalar_one())
        headers = jwt_auth_headers(user_id)

        now = _fixed_now()
        session.add_all(
            [
                MemoryMetricsHourly(
                    window_start=now - dt.timedelta(hours=1),
                    window_duration=3600,
                    total_requests=100,
                    retrieval_triggered=60,
                    retrieval_success=40,
                    retrieval_empty=20,
                    retrieval_error=0,
                    memory_hits=30,
                    memory_misses=30,
                    retrieval_latency_avg_ms=200.0,
                    retrieval_latency_p95_ms=500.0,
                    routing_requests=10,
                    routing_stored_user=2,
                    routing_stored_system=3,
                    session_count=5,
                    backlog_batches_sum=10,
                    backlog_batches_max=4,
                ),
                MemoryMetricsHourly(
                    window_start=now - dt.timedelta(hours=2),
                    window_duration=3600,
                    total_requests=50,
                    retrieval_triggered=10,
                    retrieval_success=5,
                    retrieval_empty=5,
                    retrieval_error=0,
                    memory_hits=5,
                    memory_misses=5,
                    retrieval_latency_avg_ms=1000.0,
                    retrieval_latency_p95_ms=2000.0,
                    routing_requests=5,
                    routing_stored_user=1,
                    routing_stored_system=1,
                    session_count=1,
                    backlog_batches_sum=3,
                    backlog_batches_max=3,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        resp = client.get("/metrics/memory/kpis?time_range=7d", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

    assert data["time_range"] == "7d"
    assert data["total_requests"] == 150
    assert data["retrieval_triggered"] == 70

    # retrieval_skipped/hourly: total_requests - retrieval_triggered
    assert data["retrieval_skipped"] == (100 - 60) + (50 - 10)

    # routing_skipped/hourly: routing_requests - stored_user - stored_system
    assert data["routing_skipped"] == (10 - 2 - 3) + (5 - 1 - 1)

    # latency_avg/hourly: sum(avg_ms * triggered) / sum(triggered)
    expected_latency_avg = (200.0 * 60 + 1000.0 * 10) / 70
    expected_latency_p95 = (500.0 * 60 + 2000.0 * 10) / 70

    assert data["retrieval_latency_avg_ms"] == pytest.approx(expected_latency_avg)
    assert data["retrieval_latency_p95_ms"] == pytest.approx(expected_latency_p95)
    assert data["backlog_batches_max"] == 4


def test_memory_pulse_hourly_uses_weighted_latency(app_with_inmemory_db, monkeypatch):
    app, SessionLocal = app_with_inmemory_db

    from app.api import memory_metrics_routes

    monkeypatch.setattr(memory_metrics_routes, "_utc_now", _fixed_now)

    with SessionLocal() as session:
        user_id = str(session.execute(select(User.id)).scalar_one())
        headers = jwt_auth_headers(user_id)

        now = _fixed_now()
        window_start = now - dt.timedelta(hours=2)

        # Two rows in the same hour bucket; pulse groups by window_start, so latency must be weighted by triggered.
        session.add_all(
            [
                MemoryMetricsHourly(
                    user_id=None,
                    project_id=None,
                    window_start=window_start,
                    window_duration=3600,
                    total_requests=10,
                    retrieval_triggered=10,
                    retrieval_success=10,
                    retrieval_empty=0,
                    retrieval_error=0,
                    memory_hits=5,
                    memory_misses=5,
                    retrieval_latency_avg_ms=100.0,
                    retrieval_latency_p95_ms=300.0,
                    routing_requests=0,
                    routing_stored_user=0,
                    routing_stored_system=0,
                    session_count=1,
                    backlog_batches_sum=0,
                    backlog_batches_max=0,
                ),
                MemoryMetricsHourly(
                    user_id=None,
                    project_id=None,
                    window_start=window_start,
                    window_duration=3600,
                    total_requests=10,
                    retrieval_triggered=1,
                    retrieval_success=1,
                    retrieval_empty=0,
                    retrieval_error=0,
                    memory_hits=1,
                    memory_misses=0,
                    retrieval_latency_avg_ms=1000.0,
                    retrieval_latency_p95_ms=1200.0,
                    routing_requests=0,
                    routing_stored_user=0,
                    routing_stored_system=0,
                    session_count=1,
                    backlog_batches_sum=0,
                    backlog_batches_max=0,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        resp = client.get(
            "/metrics/memory/pulse?time_range=7d&granularity=hour",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()

    assert data["time_range"] == "7d"
    assert data["granularity"] == "hour"
    assert len(data["points"]) >= 1

    def _parse_ts(value: str) -> dt.datetime:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed

    # Find the point for our window_start (SQLite 时区序列化可能不稳定，按解析后的 datetime 匹配)
    point = None
    for candidate in data["points"]:
        if _parse_ts(candidate["window_start"]) == window_start:
            point = candidate
            break
    assert point is not None

    assert point["total_requests"] == 20
    assert point["retrieval_triggered"] == 11

    expected_latency_avg = (100.0 * 10 + 1000.0 * 1) / 11
    assert point["retrieval_latency_avg_ms"] == pytest.approx(expected_latency_avg)
