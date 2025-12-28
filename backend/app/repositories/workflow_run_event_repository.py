from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import WorkflowRunEvent


def append_workflow_run_event(
    db: Session,
    *,
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None,
) -> WorkflowRunEvent:
    """
    追加一条 WorkflowRunEvent（append-only）。

    注意：当前实现通过 `max(seq)+1` 分配序号，适用于“单执行者”或低并发场景。
    如后续引入多 worker 并发写同一 run，需要替换为更严格的序列分配策略。
    """
    last_error: Exception | None = None
    for _ in range(5):
        next_seq = db.execute(
            select(func.max(WorkflowRunEvent.seq)).where(WorkflowRunEvent.run_id == run_id)
        ).scalar_one()
        seq = int(next_seq or 0) + 1

        row = WorkflowRunEvent(
            run_id=run_id,
            seq=seq,
            event_type=str(event_type or "").strip() or "event",
            payload=payload or {},
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError as exc:
            # 并发追加导致 seq 冲突：回滚后重试分配（v0 通过重试降低偶发失败概率）
            last_error = exc
            db.rollback()
            continue
        else:
            db.refresh(row)
            return row

    raise last_error or RuntimeError("append_workflow_run_event failed")


def list_workflow_run_events(
    db: Session,
    *,
    run_id: UUID,
    after_seq: int | None = None,
    limit: int = 200,
) -> list[WorkflowRunEvent]:
    limit = max(1, min(int(limit or 200), 1000))
    stmt = select(WorkflowRunEvent).where(WorkflowRunEvent.run_id == run_id)
    if after_seq is not None:
        stmt = stmt.where(WorkflowRunEvent.seq > int(after_seq))
    stmt = stmt.order_by(WorkflowRunEvent.seq.asc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


__all__ = ["append_workflow_run_event", "list_workflow_run_events"]
