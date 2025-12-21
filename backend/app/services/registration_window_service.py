from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import RegistrationWindow, RegistrationWindowStatus


class RegistrationWindowError(Exception):
    """Base error for registration window operations."""


class RegistrationWindowNotFoundError(RegistrationWindowError):
    """Raised when no window is available."""


class RegistrationWindowClosedError(RegistrationWindowError):
    """Raised when the window is already closed or expired."""


class RegistrationQuotaExceededError(RegistrationWindowError):
    """Raised when no remaining slots are available."""


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC to avoid naive/aware comparison issues."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _now(now: datetime | None = None) -> datetime:
    """Return a timezone-aware UTC 'now' value."""
    if now is None:
        return datetime.now(UTC)
    return _ensure_utc(now)


def _sync_window_states(session: Session, *, now: datetime) -> None:
    """Promote due windows to active and close expired ones."""

    now = _ensure_utc(now)

    # Activate scheduled windows whose start_time has arrived
    due_stmt: Select[tuple[RegistrationWindow]] = select(RegistrationWindow).where(
        RegistrationWindow.status == RegistrationWindowStatus.SCHEDULED,
        RegistrationWindow.start_time <= now,
        RegistrationWindow.end_time >= now,
    )
    updated = False
    for window in session.execute(due_stmt).scalars().all():
        window.status = RegistrationWindowStatus.ACTIVE
        updated = True

    # Close active windows that are already past the end time
    expired_stmt: Select[tuple[RegistrationWindow]] = select(RegistrationWindow).where(
        RegistrationWindow.status == RegistrationWindowStatus.ACTIVE,
        RegistrationWindow.end_time < now,
    )
    for window in session.execute(expired_stmt).scalars().all():
        window.status = RegistrationWindowStatus.CLOSED
        updated = True

    if updated:
        session.commit()


def _select_active_window_stmt(now: datetime) -> Select[tuple[RegistrationWindow]]:
    return (
        select(RegistrationWindow)
        .where(RegistrationWindow.status == RegistrationWindowStatus.ACTIVE)
        .where(RegistrationWindow.start_time <= now)
        .where(RegistrationWindow.end_time >= now)
        .where(RegistrationWindow.registered_count < RegistrationWindow.max_registrations)
        .order_by(RegistrationWindow.start_time)
        .limit(1)
    )


def create_registration_window(
    session: Session,
    *,
    start_time: datetime,
    end_time: datetime,
    max_registrations: int,
    auto_activate: bool = True,
) -> RegistrationWindow:
    start_time = _ensure_utc(start_time)
    end_time = _ensure_utc(end_time)

    if max_registrations <= 0:
        raise ValueError("max_registrations must be greater than zero")
    if end_time <= start_time:
        raise ValueError("end_time must be later than start_time")

    window = RegistrationWindow(
        start_time=start_time,
        end_time=end_time,
        max_registrations=max_registrations,
        auto_activate=auto_activate,
        status=RegistrationWindowStatus.SCHEDULED,
    )
    if start_time <= _now():
        window.status = RegistrationWindowStatus.ACTIVE

    session.add(window)
    session.commit()
    session.refresh(window)

    _schedule_window_tasks(window)
    return window


def _schedule_window_tasks(window: RegistrationWindow) -> None:
    """Schedule Celery tasks for activation/closure; log and continue on failures.

    在测试环境下（通过检测 pytest 注入的环境变量）直接跳过 Celery 调度，
    避免因无法连接 broker 而导致测试长时间卡住。
    """

    # pytest 在运行测试时会设置 PYTEST_CURRENT_TEST 环境变量；
    # 利用这一点在单元测试中禁用真正的异步任务调度。
    if os.getenv("PYTEST_CURRENT_TEST"):
        return

    try:
        from app.tasks.registration import (
            activate_registration_window,
            close_registration_window,
        )

        activate_registration_window.apply_async(
            args=[str(window.id)],
            eta=window.start_time,
        )
        close_registration_window.apply_async(
            args=[str(window.id)],
            eta=window.end_time,
        )
    except Exception:
        logger.warning(
            "Failed to schedule registration window tasks for %s; will rely on runtime checks",
            window.id,
            exc_info=True,
        )


def get_active_registration_window(
    session: Session, *, now: datetime | None = None
) -> RegistrationWindow | None:
    current_time = _now(now)
    _sync_window_states(session, now=current_time)
    return session.execute(_select_active_window_stmt(current_time)).scalar_one_or_none()


def activate_window_by_id(session: Session, window_id) -> RegistrationWindow | None:
    window = session.get(RegistrationWindow, window_id)
    if window is None:
        return None
    if window.status == RegistrationWindowStatus.CLOSED:
        return window

    current_time = _now()
    window_start = _ensure_utc(window.start_time)
    window_end = _ensure_utc(window.end_time)
    if window_start <= current_time <= window_end:
        window.status = RegistrationWindowStatus.ACTIVE
    elif window_end < current_time:
        window.status = RegistrationWindowStatus.CLOSED
    session.commit()
    session.refresh(window)
    return window


def close_window_by_id(session: Session, window_id) -> RegistrationWindow | None:
    window = session.get(RegistrationWindow, window_id)
    if window is None:
        return None
    if window.status == RegistrationWindowStatus.CLOSED:
        return window

    window.status = RegistrationWindowStatus.CLOSED
    session.commit()
    session.refresh(window)
    return window


def claim_registration_slot(
    session: Session, *, now: datetime | None = None
) -> RegistrationWindow:
    current_time = _now(now)
    _sync_window_states(session, now=current_time)

    window = session.execute(_select_active_window_stmt(current_time)).scalar_one_or_none()
    if window is None:
        raise RegistrationWindowNotFoundError("当前未开放注册窗口")

    window_end = _ensure_utc(window.end_time)

    if window_end < current_time:
        window.status = RegistrationWindowStatus.CLOSED
        session.commit()
        raise RegistrationWindowClosedError("注册时间已结束")

    if window.registered_count >= window.max_registrations:
        window.status = RegistrationWindowStatus.CLOSED
        session.commit()
        raise RegistrationQuotaExceededError("注册名额已满")

    window.registered_count += 1
    if window.registered_count >= window.max_registrations:
        window.status = RegistrationWindowStatus.CLOSED
    session.commit()
    session.refresh(window)
    return window


def rollback_registration_slot(
    session: Session, window_id, *, now: datetime | None = None
) -> None:
    window = session.get(RegistrationWindow, window_id)
    if window is None:
        return

    current_time = _now(now)
    if window.registered_count > 0:
        window.registered_count -= 1
    window_start = _ensure_utc(window.start_time)
    window_end = _ensure_utc(window.end_time)
    if (
        window.status == RegistrationWindowStatus.CLOSED
        and window.registered_count < window.max_registrations
        and window_end >= current_time
        and window_start <= current_time
    ):
        window.status = RegistrationWindowStatus.ACTIVE

    session.commit()


__all__ = [
    "RegistrationQuotaExceededError",
    "RegistrationWindowClosedError",
    "RegistrationWindowError",
    "RegistrationWindowNotFoundError",
    "activate_window_by_id",
    "claim_registration_slot",
    "close_window_by_id",
    "create_registration_window",
    "get_active_registration_window",
    "rollback_registration_slot",
]
