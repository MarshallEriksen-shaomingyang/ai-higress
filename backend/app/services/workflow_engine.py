from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.db import SessionLocal
from app.logging_config import logger
from app.models import WorkflowRun
from app.redis_client import get_redis_client
from app.repositories.workflow_run_event_repository import append_workflow_run_event
from app.schemas.workflow import WorkflowSpec
from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.workflow_run_event_bus import (
    build_workflow_run_event_envelope,
    publish_workflow_run_event_best_effort,
)
from app.services.workflow_bridge_dispatcher import BridgeStreamDispatcher, WorkflowInvocationMeta


DEFAULT_TOOL_TIMEOUT_MS = 60000
MAX_LOG_PREVIEW_CHARS = 8000


def _utc_now() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)


def _append_preview(existing: str, addition: str, *, limit: int = MAX_LOG_PREVIEW_CHARS) -> str:
    if not addition:
        return existing
    merged = (existing or "") + addition
    if len(merged) <= limit:
        return merged
    return merged[-limit:]


def _ensure_steps_state(state: Any) -> dict[str, Any]:
    return state if isinstance(state, dict) else {}


def _ensure_step_entry(steps_state: dict[str, Any], step_id: str) -> dict[str, Any]:
    entry = steps_state.get(step_id)
    if not isinstance(entry, dict):
        entry = {}
        steps_state[step_id] = entry
    return entry


def _ensure_attempts(entry: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = entry.get("attempts")
    if not isinstance(attempts, list):
        attempts = []
        entry["attempts"] = attempts
    return attempts


@dataclass(slots=True)
class SpawnResult:
    started: bool
    message: str


class WorkflowEngine:
    """
    串行工作流执行引擎（v0）：
    - 严格串行（current_step_index 指针）
    - 每步可选人工审批（approval_policy=manual）
    - 失败默认“红色暂停”（paused_reason=step_failed），供用户重试
    """

    def __init__(self, dispatcher: BridgeStreamDispatcher) -> None:
        self._dispatcher = dispatcher
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def spawn(self, run_id: UUID) -> SpawnResult:
        key = str(run_id)
        async with self._lock:
            existing = self._tasks.get(key)
            if existing is not None and not existing.done():
                return SpawnResult(started=False, message="already_running_in_process")
            task = asyncio.create_task(self._run_loop(run_id), name=f"workflow-engine:{key}")
            self._tasks[key] = task
            task.add_done_callback(lambda _: self._tasks.pop(key, None))
            return SpawnResult(started=True, message="spawned")

    async def cancel_local(self, run_id: UUID) -> None:
        key = str(run_id)
        async with self._lock:
            task = self._tasks.get(key)
        if task is not None and not task.done():
            task.cancel()

    async def _run_loop(self, run_id: UUID) -> None:
        client = BridgeGatewayClient()
        await self._dispatcher.start()

        while True:
            db = SessionLocal()
            try:
                run: WorkflowRun | None = db.get(WorkflowRun, run_id)
                if run is None:
                    logger.warning("workflow_engine: run not found run_id=%s", run_id)
                    return
                if str(run.status or "") != "running":
                    return

                try:
                    spec = WorkflowSpec.model_validate(run.workflow_snapshot)
                except Exception as exc:
                    run.status = "failed"
                    run.error_code = "INVALID_SPEC"
                    run.error_message = f"invalid workflow_snapshot: {exc}"
                    run.finished_at = _utc_now()
                    db.add(run)
                    db.commit()
                    await self._emit_event(
                        run_id=run_id,
                        event_type="run.failed",
                        payload={
                            "type": "run.failed",
                            "run_id": str(run_id),
                            "error_code": "INVALID_SPEC",
                            "message": str(run.error_message or "")[:800],
                        },
                    )
                    return

                idx = int(run.current_step_index or 0)
                if idx >= len(spec.steps):
                    run.status = "completed"
                    run.paused_reason = None
                    run.finished_at = _utc_now()
                    db.add(run)
                    db.commit()
                    await self._emit_event(
                        run_id=run_id,
                        event_type="run.completed",
                        payload={"type": "run.completed", "run_id": str(run_id)},
                    )
                    return

                step = spec.steps[idx]
                steps_state = _ensure_steps_state(run.steps_state)
                entry = _ensure_step_entry(steps_state, step.id)
                _status = str(entry.get("status") or "pending")

                if step.approval_policy == "manual" and not bool(entry.get("approved", False)):
                    run.status = "paused"
                    run.paused_reason = "awaiting_approval"
                    run.steps_state = steps_state
                    run.last_activity_at = _utc_now()
                    db.add(run)
                    db.commit()
                    await self._emit_event(
                        run_id=run_id,
                        event_type="step.paused",
                        payload={
                            "type": "step.paused",
                            "run_id": str(run_id),
                            "step_id": step.id,
                            "paused_reason": "awaiting_approval",
                            "current_step_index": idx,
                        },
                    )
                    return

                # 开始/重试当前 step
                attempts = _ensure_attempts(entry)
                attempt_index = len(attempts)
                req_id = f"wf_{uuid.uuid4().hex}"
                attempt: dict[str, Any] = {
                    "req_id": req_id,
                    "agent_id": step.tool_config.agent_id,
                    "tool_name": step.tool_config.tool_name,
                    "start_ts": int(time.time()),
                    "end_ts": None,
                    "ok": None,
                    "exit_code": None,
                    "canceled": None,
                    "error": None,
                    "result_json": None,
                    "result_preview": None,
                    "log_preview": "",
                }
                attempts.append(attempt)
                entry["status"] = "running"
                entry["attempts"] = attempts
                run.steps_state = steps_state
                run.paused_reason = None
                run.last_activity_at = _utc_now()
                if run.started_at is None:
                    run.started_at = _utc_now()
                db.add(run)
                db.commit()

            finally:
                db.close()

            await self._emit_event(
                run_id=run_id,
                event_type="step.progress",
                payload={
                    "type": "step.progress",
                    "run_id": str(run_id),
                    "step_id": step.id,
                    "status": "running",
                    "current_step_index": idx,
                    "attempt_index": attempt_index,
                },
            )
            await self._emit_event(
                run_id=run_id,
                event_type="tool.status",
                payload={
                    "type": "tool.status",
                    "run_id": str(run_id),
                    "step_id": step.id,
                    "req_id": req_id,
                    "agent_id": step.tool_config.agent_id,
                    "tool_name": step.tool_config.tool_name,
                    "attempt_index": attempt_index,
                    "state": "running",
                },
            )

            # 注册等待者（用于接收 RESULT/LOG）
            fut = await self._dispatcher.register(
                WorkflowInvocationMeta(
                    run_id=str(run_id),
                    step_id=step.id,
                    req_id=req_id,
                    agent_id=step.tool_config.agent_id,
                    tool_name=step.tool_config.tool_name,
                    attempt_index=attempt_index,
                )
            )

            # 调用 Bridge（传入我们自己的 req_id，便于后续匹配）
            timeout_ms = int(step.tool_config.timeout_ms or DEFAULT_TOOL_TIMEOUT_MS)
            stream = bool(step.tool_config.stream) if step.tool_config.stream is not None else True
            try:
                await client.invoke(
                    req_id=req_id,
                    agent_id=step.tool_config.agent_id,
                    tool_name=step.tool_config.tool_name,
                    arguments=step.tool_config.arguments,
                    timeout_ms=timeout_ms,
                    stream=stream,
                )
            except httpx.RequestError as exc:
                await self._dispatcher.abort(req_id=req_id, reason="bridge_unavailable")
                await self._pause_failed(
                    run_id=run_id,
                    step_id=step.id,
                    req_id=req_id,
                    message=f"Bridge Gateway 不可用: {exc}",
                    on_error=step.on_error,
                )
                continue
            except httpx.HTTPStatusError as exc:
                await self._dispatcher.abort(req_id=req_id, reason="bridge_error")
                await self._pause_failed(
                    run_id=run_id,
                    step_id=step.id,
                    req_id=req_id,
                    message=f"Bridge Gateway 调用失败: {exc.response.status_code if exc.response else 'unknown'}",
                    on_error=step.on_error,
                )
                continue

            # 等待 RESULT（超时按 timeout 处理）
            try:
                result_payload = await asyncio.wait_for(fut, timeout=float(timeout_ms) / 1000.0 + 5.0)
            except asyncio.TimeoutError:
                await self._dispatcher.abort(req_id=req_id, reason="invoke_timeout")
                await self._pause_failed(
                    run_id=run_id,
                    step_id=step.id,
                    req_id=req_id,
                    message="tool invoke timed out",
                    on_error=step.on_error,
                    error_code="invoke_timeout",
                )
                continue
            except Exception as exc:
                await self._pause_failed(
                    run_id=run_id,
                    step_id=step.id,
                    req_id=req_id,
                    message=f"invoke aborted: {exc}",
                    on_error=step.on_error,
                )
                continue

            ok = bool(result_payload.get("ok", False)) if isinstance(result_payload, dict) else False
            if ok:
                await self._mark_step_succeeded(run_id=run_id, step_id=step.id, req_id=req_id, result=result_payload)
                await self._emit_event(
                    run_id=run_id,
                    event_type="step.completed",
                    payload={
                        "type": "step.completed",
                        "run_id": str(run_id),
                        "step_id": step.id,
                        "current_step_index": idx,
                    },
                )
            else:
                err = None
                if isinstance(result_payload, dict):
                    err = result_payload.get("error")
                paused = await self._pause_failed(
                    run_id=run_id,
                    step_id=step.id,
                    req_id=req_id,
                    message=str(err)[:800] if err is not None else "tool failed",
                    on_error=step.on_error,
                )
                await self._emit_event(
                    run_id=run_id,
                    event_type="step.progress",
                    payload={
                        "type": "step.progress",
                        "run_id": str(run_id),
                        "step_id": step.id,
                        "status": "failed",
                        "current_step_index": idx,
                    },
                )
                if paused:
                    await self._emit_event(
                        run_id=run_id,
                        event_type="step.paused",
                        payload={
                            "type": "step.paused",
                            "run_id": str(run_id),
                            "step_id": step.id,
                            "paused_reason": "step_failed",
                            "current_step_index": idx,
                        },
                    )

    async def approve_current_step(self, run_id: UUID) -> bool:
        db = SessionLocal()
        try:
            run: WorkflowRun | None = db.get(WorkflowRun, run_id)
            if run is None:
                return False
            if str(run.status or "") != "paused":
                return False
            try:
                spec = WorkflowSpec.model_validate(run.workflow_snapshot)
            except Exception:
                return False
            idx = int(run.current_step_index or 0)
            if idx >= len(spec.steps):
                return False
            step_id = spec.steps[idx].id
            steps_state = _ensure_steps_state(run.steps_state)
            entry = _ensure_step_entry(steps_state, step_id)
            entry["approved"] = True
            entry["approved_at"] = int(time.time())
            run.steps_state = steps_state
            run.last_activity_at = _utc_now()
            db.add(run)
            db.commit()
            return True
        finally:
            db.close()

    async def _pause_failed(
        self,
        *,
        run_id: UUID,
        step_id: str,
        req_id: str,
        message: str,
        on_error: str,
        error_code: str | None = None,
    ) -> bool:
        db = SessionLocal()
        try:
            run: WorkflowRun | None = db.get(WorkflowRun, run_id)
            if run is None:
                return True
            steps_state = _ensure_steps_state(run.steps_state)
            entry = _ensure_step_entry(steps_state, step_id)
            entry["status"] = "failed"

            attempts = _ensure_attempts(entry)
            for at in reversed(attempts):
                if str(at.get("req_id") or "") == req_id:
                    at["end_ts"] = int(time.time())
                    at["ok"] = False
                    at["error"] = {"code": error_code, "message": message} if error_code else {"message": message}
                    at["log_preview"] = _append_preview(str(at.get("log_preview") or ""), "")
                    break

            run.steps_state = steps_state
            run.last_activity_at = _utc_now()
            if str(on_error or "") == "continue":
                run.current_step_index = int(run.current_step_index or 0) + 1
                run.paused_reason = None
                db.add(run)
                db.commit()
                return False

            run.status = "paused"
            run.paused_reason = "step_failed"
            run.error_code = error_code or "STEP_FAILED"
            run.error_message = message[:800]
            db.add(run)
            db.commit()
            return True
        finally:
            db.close()

    async def _mark_step_succeeded(self, *, run_id: UUID, step_id: str, req_id: str, result: dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            run: WorkflowRun | None = db.get(WorkflowRun, run_id)
            if run is None:
                return
            steps_state = _ensure_steps_state(run.steps_state)
            entry = _ensure_step_entry(steps_state, step_id)
            entry["status"] = "success"
            attempts = _ensure_attempts(entry)

            result_preview = None
            try:
                if result.get("result_json") is not None:
                    import json

                    result_preview = json.dumps(result.get("result_json"), ensure_ascii=False)[:800]
                elif isinstance(result.get("error"), dict):
                    err = result.get("error") or {}
                    result_preview = str(err.get("message") or err.get("code") or "")[:800] or None
            except Exception:
                result_preview = None

            for at in reversed(attempts):
                if str(at.get("req_id") or "") == req_id:
                    at["end_ts"] = int(time.time())
                    at["ok"] = True
                    at["exit_code"] = int(result.get("exit_code") or 0)
                    at["canceled"] = bool(result.get("canceled", False))
                    at["error"] = result.get("error")
                    at["result_json"] = result.get("result_json")
                    at["result_preview"] = result_preview
                    break
            run.steps_state = steps_state
            run.current_step_index = int(run.current_step_index or 0) + 1
            run.last_activity_at = _utc_now()
            run.paused_reason = None
            run.error_code = None
            run.error_message = None
            db.add(run)
            db.commit()
        finally:
            db.close()

    async def _emit_event(self, *, run_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            ev = append_workflow_run_event(
                db,
                run_id=run_id,
                event_type=event_type,
                payload=payload,
            )
            created_at_iso = None
            try:
                created_at_iso = ev.created_at.isoformat() if getattr(ev, "created_at", None) is not None else None
            except Exception:
                created_at_iso = None
            envelope = build_workflow_run_event_envelope(
                run_id=run_id,
                seq=int(getattr(ev, "seq", 0) or 0),
                event_type=event_type,
                created_at_iso=created_at_iso,
                payload=payload,
            )
        finally:
            db.close()

        try:
            redis = get_redis_client()
        except Exception:
            redis = None
        publish_workflow_run_event_best_effort(redis, run_id=run_id, envelope=envelope)


__all__ = ["WorkflowEngine", "DEFAULT_TOOL_TIMEOUT_MS"]
