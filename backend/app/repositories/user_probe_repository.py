from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Provider
from app.models.user_probe import UserProbeRun, UserProbeTask


def count_user_tasks(db: Session, *, user_id: UUID) -> int:
    stmt = select(func.count()).select_from(UserProbeTask).where(UserProbeTask.user_id == user_id)
    return int(db.execute(stmt).scalar() or 0)


def create_task(db: Session, *, task: UserProbeTask) -> UserProbeTask:
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(
    db: Session,
    *,
    user_id: UUID,
    provider_uuid: object,
) -> list[UserProbeTask]:
    stmt: Select[tuple[UserProbeTask]] = (
        select(UserProbeTask)
        .where(UserProbeTask.user_id == user_id)
        .where(UserProbeTask.provider_uuid == provider_uuid)
        .options(selectinload(UserProbeTask.last_run))
        .order_by(UserProbeTask.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_task(
    db: Session,
    *,
    user_id: UUID,
    provider_uuid: object,
    task_id: UUID,
) -> UserProbeTask | None:
    stmt: Select[tuple[UserProbeTask]] = (
        select(UserProbeTask)
        .where(UserProbeTask.id == task_id)
        .where(UserProbeTask.user_id == user_id)
        .where(UserProbeTask.provider_uuid == provider_uuid)
        .options(selectinload(UserProbeTask.last_run))
    )
    return db.execute(stmt).scalars().first()


def persist_task(db: Session, *, task: UserProbeTask) -> UserProbeTask:
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, *, task: UserProbeTask) -> None:
    db.delete(task)
    db.commit()


def list_runs(db: Session, *, task_id: UUID, limit: int) -> list[UserProbeRun]:
    limit_value = max(1, min(int(limit), 200))
    stmt: Select[tuple[UserProbeRun]] = (
        select(UserProbeRun)
        .where(UserProbeRun.task_uuid == task_id)
        .order_by(UserProbeRun.created_at.desc())
        .limit(limit_value)
    )
    return list(db.execute(stmt).scalars().all())


def mark_task_in_progress(db: Session, *, task: UserProbeTask, in_progress: bool) -> None:
    task.in_progress = bool(in_progress)
    db.add(task)
    db.commit()


def prune_task_runs(db: Session, *, task_id: UUID, keep: int) -> None:
    keep_value = max(1, int(keep))
    sub = (
        select(UserProbeRun.id)
        .where(UserProbeRun.task_uuid == task_id)
        .order_by(UserProbeRun.created_at.desc())
        .offset(keep_value)
    )
    ids = [row[0] for row in db.execute(sub).all()]
    if not ids:
        return
    db.execute(delete(UserProbeRun).where(UserProbeRun.id.in_(ids)))


def save_run_and_update_task(
    db: Session,
    *,
    task: UserProbeTask,
    provider: Provider,
    run: UserProbeRun,
    finished_at: datetime,
    next_run_at: datetime | None,
    keep_runs: int,
) -> UserProbeRun:
    db.add(run)
    db.flush()  # ensure run.id

    task.last_run_at = finished_at
    task.last_run_uuid = run.id
    task.next_run_at = next_run_at
    db.add(task)

    prune_task_runs(db, task_id=task.id, keep=keep_runs)
    db.commit()
    db.refresh(run)
    db.refresh(task)
    return run


def select_due_tasks_for_update(
    db: Session,
    *,
    now: datetime,
    limit: int,
) -> list[UserProbeTask]:
    stmt = (
        select(UserProbeTask)
        .where(UserProbeTask.enabled.is_(True))
        .where(UserProbeTask.in_progress.is_(False))
        .where((UserProbeTask.next_run_at.is_(None)) | (UserProbeTask.next_run_at <= now))
        .order_by(UserProbeTask.next_run_at.asc().nullsfirst(), UserProbeTask.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(db.execute(stmt).scalars().all())


def mark_tasks_in_progress(db: Session, *, tasks: Sequence[UserProbeTask]) -> None:
    for t in tasks:
        t.in_progress = True
        db.add(t)
    db.commit()


def get_provider_by_uuid(db: Session, *, provider_uuid: object) -> Provider | None:
    try:
        return db.get(Provider, provider_uuid)
    except Exception:
        return None


def persist_task_state(db: Session, *, task: UserProbeTask) -> None:
    db.add(task)
    db.commit()


__all__ = [
    "count_user_tasks",
    "create_task",
    "delete_task",
    "get_provider_by_uuid",
    "get_task",
    "list_runs",
    "list_tasks",
    "mark_task_in_progress",
    "mark_tasks_in_progress",
    "persist_task",
    "persist_task_state",
    "prune_task_runs",
    "save_run_and_update_task",
    "select_due_tasks_for_update",
]

