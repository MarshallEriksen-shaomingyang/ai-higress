from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.models import RegistrationWindowStatus
from app.services.registration_window_service import create_registration_window


def test_register_blocked_without_window(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "Secret123", "display_name": "User"},
    )

    assert response.status_code == 403
    assert "当前未开放注册窗口" in response.text


def test_register_auto_activation_window(app_with_inmemory_db) -> None:
    app, SessionLocal = app_with_inmemory_db
    start = datetime.now(UTC) - timedelta(minutes=1)
    end = datetime.now(UTC) + timedelta(minutes=5)

    with SessionLocal() as session:
        create_registration_window(
            session,
            start_time=start,
            end_time=end,
            max_registrations=1,
            auto_activate=True,
        )

    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "auto@example.com", "password": "Secret123", "display_name": "Auto"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["is_active"] is True

    with SessionLocal() as session:
        status = session.execute(
            text("select status from registration_windows limit 1")
        ).scalar_one()
        assert status == RegistrationWindowStatus.CLOSED.value


def test_register_manual_activation_window(app_with_inmemory_db) -> None:
    app, SessionLocal = app_with_inmemory_db
    start = datetime.now(UTC) - timedelta(minutes=1)
    end = datetime.now(UTC) + timedelta(minutes=5)

    with SessionLocal() as session:
        create_registration_window(
            session,
            start_time=start,
            end_time=end,
            max_registrations=2,
            auto_activate=False,
        )

    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "manual@example.com", "password": "Secret123", "display_name": "Manual"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["is_active"] is False

    with SessionLocal() as session:
        row = session.execute(
            text(
                "select registered_count, status, auto_activate from registration_windows limit 1"
            )
        ).one()
        assert row.registered_count == 1
        assert row.status == RegistrationWindowStatus.ACTIVE.value
        # SQLite 中布尔字段通过原始 SQL 查询返回为 0/1，这里显式转为 bool 以保证断言稳定
        assert bool(row.auto_activate) is False
