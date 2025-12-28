from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.errors import forbidden, http_error, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Workflow, WorkflowRun
from app.repositories.workflow_run_event_repository import list_workflow_run_events
from app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowRunCancelRequest,
    WorkflowRunCreateRequest,
    WorkflowRunResponse,
)
from app.schemas.workflow import WorkflowSpec
from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.workflow_runtime import get_workflow_runtime


router = APIRouter(
    tags=["workflows"],
    dependencies=[Depends(require_jwt_token)],
)


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    try:
        return dt.isoformat()
    except Exception:
        return ""


def _encode_sse_event(*, event_type: str, data: Any) -> bytes:
    lines: list[str] = []
    event = str(event_type or "").strip()
    if event:
        lines.append(f"event: {event}")
    if isinstance(data, (bytes, bytearray)):
        payload = data.decode("utf-8", errors="ignore")
        lines.append(f"data: {payload}")
    elif isinstance(data, str):
        lines.append(f"data: {data}")
    else:
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")

def _decode_pubsub_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = value.decode("utf-8", errors="ignore")
    elif isinstance(value, str):
        raw = value
    else:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _ensure_owner(*, current_user: AuthenticatedUser, owner_user_id: UUID) -> None:
    if UUID(str(current_user.id)) != UUID(str(owner_user_id)):
        raise forbidden("无权限访问该资源")


@router.post("/v1/workflows", response_model=WorkflowResponse)
def create_workflow_endpoint(
    payload: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> WorkflowResponse:
    spec = payload.spec.model_copy(deep=True)
    spec.title = payload.title
    spec.description = payload.description

    row = Workflow(
        user_id=UUID(str(current_user.id)),
        title=payload.title,
        description=payload.description,
        spec_json=spec.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return WorkflowResponse(
        workflow_id=row.id,
        title=row.title,
        description=row.description,
        spec=spec,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


@router.post("/v1/workflow-runs", response_model=WorkflowRunResponse)
async def create_workflow_run_endpoint(
    payload: WorkflowRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> WorkflowRunResponse:
    wf: Workflow | None = db.get(Workflow, payload.workflow_id)
    if wf is None:
        raise not_found("Workflow 不存在")
    _ensure_owner(current_user=current_user, owner_user_id=wf.user_id)

    snapshot = wf.spec_json if isinstance(wf.spec_json, dict) else {}

    run = WorkflowRun(
        workflow_id=wf.id,
        user_id=UUID(str(current_user.id)),
        status="running",
        paused_reason=None,
        current_step_index=0,
        workflow_snapshot=snapshot,
        steps_state={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    runtime = get_workflow_runtime()
    await runtime.spawn_run(run.id)

    return WorkflowRunResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        paused_reason=run.paused_reason,
        current_step_index=int(run.current_step_index or 0),
        workflow_snapshot=payload_from_snapshot(run.workflow_snapshot),
        steps_state=run.steps_state if isinstance(run.steps_state, dict) else {},
        created_at=_iso(run.created_at),
        updated_at=_iso(run.updated_at),
    )


@router.get("/v1/workflow-runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run_endpoint(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> WorkflowRunResponse:
    run: WorkflowRun | None = db.get(WorkflowRun, run_id)
    if run is None:
        raise not_found("WorkflowRun 不存在")
    _ensure_owner(current_user=current_user, owner_user_id=run.user_id)
    return WorkflowRunResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        paused_reason=run.paused_reason,
        current_step_index=int(run.current_step_index or 0),
        workflow_snapshot=payload_from_snapshot(run.workflow_snapshot),
        steps_state=run.steps_state if isinstance(run.steps_state, dict) else {},
        created_at=_iso(run.created_at),
        updated_at=_iso(run.updated_at),
    )


@router.post("/v1/workflow-runs/{run_id}/resume", response_model=WorkflowRunResponse)
async def resume_workflow_run_endpoint(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> WorkflowRunResponse:
    run: WorkflowRun | None = db.get(WorkflowRun, run_id)
    if run is None:
        raise not_found("WorkflowRun 不存在")
    _ensure_owner(current_user=current_user, owner_user_id=run.user_id)

    # 若为审批暂停，先写入 approved 标记（仍要求 paused 才允许）
    if str(run.status or "") == "paused" and str(run.paused_reason or "") == "awaiting_approval":
        await get_workflow_runtime().engine.approve_current_step(run_id)

    # CAS：只有 paused -> running 才允许启动（防止重复 resume 导致双引擎）
    res = db.execute(
        text(
            "UPDATE workflow_runs "
            "SET status='running', paused_reason=NULL "
            "WHERE id=:id AND status='paused'"
        ),
        {"id": str(run_id)},
    )
    db.commit()
    if int(getattr(res, "rowcount", 0) or 0) <= 0:
        raise http_error(409, error="conflict", message="Run 不在 paused 状态，无法 resume")

    runtime = get_workflow_runtime()
    await runtime.spawn_run(run_id)

    refreshed: WorkflowRun | None = db.get(WorkflowRun, run_id)
    if refreshed is None:
        raise not_found("WorkflowRun 不存在")
    return WorkflowRunResponse(
        run_id=refreshed.id,
        workflow_id=refreshed.workflow_id,
        status=refreshed.status,
        paused_reason=refreshed.paused_reason,
        current_step_index=int(refreshed.current_step_index or 0),
        workflow_snapshot=payload_from_snapshot(refreshed.workflow_snapshot),
        steps_state=refreshed.steps_state if isinstance(refreshed.steps_state, dict) else {},
        created_at=_iso(refreshed.created_at),
        updated_at=_iso(refreshed.updated_at),
    )


@router.post("/v1/workflow-runs/{run_id}/cancel", response_model=WorkflowRunResponse)
async def cancel_workflow_run_endpoint(
    run_id: UUID,
    payload: WorkflowRunCancelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> WorkflowRunResponse:
    run: WorkflowRun | None = db.get(WorkflowRun, run_id)
    if run is None:
        raise not_found("WorkflowRun 不存在")
    _ensure_owner(current_user=current_user, owner_user_id=run.user_id)

    if str(run.status or "") in {"completed", "failed", "canceled"}:
        return WorkflowRunResponse(
            run_id=run.id,
            workflow_id=run.workflow_id,
            status=run.status,
            paused_reason=run.paused_reason,
            current_step_index=int(run.current_step_index or 0),
            workflow_snapshot=payload_from_snapshot(run.workflow_snapshot),
            steps_state=run.steps_state if isinstance(run.steps_state, dict) else {},
            created_at=_iso(run.created_at),
            updated_at=_iso(run.updated_at),
        )

    run.status = "canceled"
    run.paused_reason = "user_cancel"
    run.finished_at = datetime.now(UTC)
    db.add(run)
    db.commit()
    db.refresh(run)

    # best-effort：停止本进程内引擎 task
    await get_workflow_runtime().cancel_local(run_id)

    # best-effort：尝试 cancel 当前在跑的工具
    try:
        _cancel_active_tool(run)
    except Exception:
        pass

    return WorkflowRunResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        paused_reason=run.paused_reason,
        current_step_index=int(run.current_step_index or 0),
        workflow_snapshot=payload_from_snapshot(run.workflow_snapshot),
        steps_state=run.steps_state if isinstance(run.steps_state, dict) else {},
        created_at=_iso(run.created_at),
        updated_at=_iso(run.updated_at),
    )


@router.get("/v1/workflow-runs/{run_id}/events")
async def stream_workflow_run_events_endpoint(
    run_id: UUID,
    request: Request,
    after_seq: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> StreamingResponse:
    run: WorkflowRun | None = db.get(WorkflowRun, run_id)
    if run is None:
        raise not_found("WorkflowRun 不存在")
    _ensure_owner(current_user=current_user, owner_user_id=run.user_id)

    last_seq = int(after_seq or 0)

    async def _gen():
        nonlocal last_seq

        # 先订阅 Redis，再做 DB replay，避免时间窗丢事件（同 run SSE 策略）
        pubsub = redis.pubsub()
        channel = f"workflow_run_events:{run_id}"
        await pubsub.subscribe(channel)
        try:
            for ev in list_workflow_run_events(db, run_id=run_id, after_seq=last_seq, limit=limit):
                seq = int(getattr(ev, "seq", 0) or 0)
                if seq <= last_seq:
                    continue
                last_seq = seq
                created_at_iso = None
                try:
                    created_at_iso = ev.created_at.isoformat() if getattr(ev, "created_at", None) is not None else None
                except Exception:
                    created_at_iso = None

                yield _encode_sse_event(
                    event_type=str(getattr(ev, "event_type", "event") or "event"),
                    data={
                        "type": "run.event",
                        "run_id": str(run_id),
                        "seq": seq,
                        "event_type": str(getattr(ev, "event_type", "event") or "event"),
                        "created_at": created_at_iso,
                        "payload": getattr(ev, "payload", None) or {},
                    },
                )

            yield _encode_sse_event(
                event_type="replay.done",
                data={"type": "replay.done", "run_id": str(run_id), "after_seq": last_seq},
            )

            while True:
                try:
                    if await request.is_disconnected():
                        break
                except Exception:  # pragma: no cover
                    break

                msg = None
                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except Exception:
                    msg = None

                if isinstance(msg, dict) and msg.get("type") == "message":
                    env = _decode_pubsub_payload(msg.get("data"))
                    if env is None:
                        continue
                    if str(env.get("type") or "") == "heartbeat":
                        continue
                    try:
                        seq = int(env.get("seq") or 0)
                    except Exception:
                        seq = 0
                    if seq <= last_seq:
                        continue
                    last_seq = seq
                    yield _encode_sse_event(event_type=str(env.get("event_type") or "event"), data=env)
                    continue
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass
            try:
                await pubsub.close()
            except Exception:
                pass

    return StreamingResponse(_gen(), media_type="text/event-stream")


def payload_from_snapshot(snapshot: Any):
    try:
        return WorkflowSpec.model_validate(snapshot)
    except Exception:
        # 如果历史数据格式不一致，至少保证接口可返回
        return WorkflowSpec(title="(invalid)", steps=[])


def _cancel_active_tool(run: WorkflowRun) -> None:
    steps_state = run.steps_state if isinstance(run.steps_state, dict) else {}
    snapshot = payload_from_snapshot(run.workflow_snapshot)
    idx = int(run.current_step_index or 0)
    if idx >= len(snapshot.steps):
        return
    step_id = snapshot.steps[idx].id
    entry = steps_state.get(step_id)
    if not isinstance(entry, dict):
        return
    attempts = entry.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return
    last = attempts[-1]
    if not isinstance(last, dict):
        return
    req_id = str(last.get("req_id") or "").strip()
    agent_id = str(last.get("agent_id") or "").strip()
    if not req_id or not agent_id:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    client = BridgeGatewayClient()
    loop.create_task(client.cancel(req_id=req_id, agent_id=agent_id, reason="user_cancel"))


__all__ = ["router"]
