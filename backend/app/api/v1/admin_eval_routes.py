from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Eval as EvalModel
from app.models import EvalRating as EvalRatingModel
from app.models import Run as RunModel
from app.schemas.admin_evals import (
    AdminEvalItem,
    AdminEvalListResponse,
    AdminEvalRatingInfo,
    AdminRunSummary,
)

router = APIRouter(
    tags=["admin-evals"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


def _parse_offset_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        value = int(cursor)
    except (TypeError, ValueError):
        return 0
    return max(value, 0)


def _next_cursor(offset: int, limit: int, *, has_more: bool) -> str | None:
    if not has_more:
        return None
    return str(offset + limit)


def _to_admin_run_summary(run: RunModel) -> AdminRunSummary:
    return AdminRunSummary(
        run_id=run.id,
        requested_logical_model=run.requested_logical_model,
        status=run.status,
        selected_provider_id=run.selected_provider_id,
        selected_provider_model=run.selected_provider_model,
        latency_ms=run.latency_ms,
        cost_credits=run.cost_credits,
        error_code=run.error_code,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _build_eval_item(
    eval_row: EvalModel,
    *,
    runs_by_id: dict[UUID, RunModel],
    ratings_by_eval_id: dict[UUID, EvalRatingModel],
) -> AdminEvalItem:
    baseline_run = runs_by_id.get(UUID(str(eval_row.baseline_run_id)))
    challenger_runs: list[AdminRunSummary] = []
    challenger_ids: list[UUID] = []
    if isinstance(eval_row.challenger_run_ids, list):
        for item in eval_row.challenger_run_ids:
            try:
                challenger_ids.append(UUID(str(item)))
            except ValueError:
                continue
    for run_id in challenger_ids:
        run = runs_by_id.get(run_id)
        if run is None:
            continue
        challenger_runs.append(_to_admin_run_summary(run))

    rating_row = ratings_by_eval_id.get(UUID(str(eval_row.id)))
    rating = (
        AdminEvalRatingInfo(
            winner_run_id=rating_row.winner_run_id,
            reason_tags=list(rating_row.reason_tags or []),
            created_at=rating_row.created_at,
        )
        if rating_row is not None
        else None
    )

    return AdminEvalItem(
        eval_id=eval_row.id,
        status=eval_row.status,
        project_id=UUID(str(eval_row.api_key_id)),
        assistant_id=UUID(str(eval_row.assistant_id)),
        baseline_run_id=UUID(str(eval_row.baseline_run_id)),
        baseline_run=_to_admin_run_summary(baseline_run) if baseline_run is not None else None,
        challengers=challenger_runs,
        explanation=eval_row.explanation,
        rated_at=eval_row.rated_at,
        rating=rating,
        created_at=eval_row.created_at,
        updated_at=eval_row.updated_at,
    )


@router.get("/admin/evals", response_model=AdminEvalListResponse)
def admin_list_evals_endpoint(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    status: str | None = Query(default=None, description="按状态过滤：running/ready/rated"),
    project_id: UUID | None = Query(default=None, description="按项目过滤（MVP: project_id == api_key_id）"),
    assistant_id: UUID | None = Query(default=None, description="按助手过滤"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminEvalListResponse:
    _ensure_admin(current_user)

    offset = _parse_offset_cursor(cursor)

    stmt: Select[tuple[EvalModel]] = select(EvalModel).order_by(EvalModel.created_at.desc())
    if status:
        stmt = stmt.where(EvalModel.status == status)
    if project_id is not None:
        stmt = stmt.where(EvalModel.api_key_id == project_id)
    if assistant_id is not None:
        stmt = stmt.where(EvalModel.assistant_id == assistant_id)

    rows = list(db.execute(stmt.offset(offset).limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    eval_rows = rows[:limit]

    eval_ids: list[UUID] = [UUID(str(r.id)) for r in eval_rows]
    run_ids: set[UUID] = set()
    for r in eval_rows:
        try:
            run_ids.add(UUID(str(r.baseline_run_id)))
        except ValueError:
            pass
        if isinstance(r.challenger_run_ids, list):
            for item in r.challenger_run_ids:
                try:
                    run_ids.add(UUID(str(item)))
                except ValueError:
                    continue

    runs_by_id: dict[UUID, RunModel] = {}
    if run_ids:
        runs = list(db.execute(select(RunModel).where(RunModel.id.in_(list(run_ids)))).scalars().all())
        runs_by_id = {UUID(str(run.id)): run for run in runs}

    ratings_by_eval_id: dict[UUID, EvalRatingModel] = {}
    if eval_ids:
        rating_rows = list(
            db.execute(select(EvalRatingModel).where(EvalRatingModel.eval_id.in_(eval_ids)))
            .scalars()
            .all()
        )
        # 评测通常只会有一条评分（eval 创建者本人），但这里仍用映射取第一条。
        for row in rating_rows:
            eid = UUID(str(row.eval_id))
            ratings_by_eval_id.setdefault(eid, row)

    items = [
        _build_eval_item(r, runs_by_id=runs_by_id, ratings_by_eval_id=ratings_by_eval_id)
        for r in eval_rows
    ]
    return AdminEvalListResponse(items=items, next_cursor=_next_cursor(offset, limit, has_more=has_more))


@router.get("/admin/evals/{eval_id}", response_model=AdminEvalItem)
def admin_get_eval_endpoint(
    eval_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminEvalItem:
    _ensure_admin(current_user)

    eval_row = db.execute(select(EvalModel).where(EvalModel.id == eval_id)).scalars().first()
    if eval_row is None:
        raise not_found("评测不存在", details={"eval_id": str(eval_id)})

    run_ids: set[UUID] = set()
    run_ids.add(UUID(str(eval_row.baseline_run_id)))
    if isinstance(eval_row.challenger_run_ids, list):
        for item in eval_row.challenger_run_ids:
            try:
                run_ids.add(UUID(str(item)))
            except ValueError:
                continue

    runs_by_id: dict[UUID, RunModel] = {}
    if run_ids:
        runs = list(db.execute(select(RunModel).where(RunModel.id.in_(list(run_ids)))).scalars().all())
        runs_by_id = {UUID(str(run.id)): run for run in runs}

    rating_row = db.execute(select(EvalRatingModel).where(EvalRatingModel.eval_id == eval_id)).scalars().first()
    ratings_by_eval_id: dict[UUID, EvalRatingModel] = {}
    if rating_row is not None:
        ratings_by_eval_id[UUID(str(rating_row.eval_id))] = rating_row

    return _build_eval_item(eval_row, runs_by_id=runs_by_id, ratings_by_eval_id=ratings_by_eval_id)


__all__ = ["router"]

