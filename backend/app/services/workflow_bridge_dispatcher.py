from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.db import SessionLocal
from app.logging_config import logger
from app.models import WorkflowRun
from app.redis_client import get_redis_client
from app.repositories.workflow_run_event_repository import append_workflow_run_event
from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.sse_parser import iter_sse_events
from app.services.workflow_run_event_bus import (
    build_workflow_run_event_envelope,
    publish_workflow_run_event_best_effort,
)


@dataclass(slots=True)
class WorkflowInvocationMeta:
    run_id: str
    step_id: str
    req_id: str
    agent_id: str
    tool_name: str
    attempt_index: int


@dataclass(slots=True)
class _Waiter:
    meta: WorkflowInvocationMeta
    future: asyncio.Future[dict[str, Any]]
    created_at: float = field(default_factory=time.monotonic)
    log_buffer: str = ""
    dropped_bytes: int = 0
    dropped_lines: int = 0
    last_flush_at: float = field(default_factory=time.monotonic)


class BridgeStreamDispatcher:
    """
    进程内全局 Bridge SSE 消费者：
    - 仅维护 1 条到 Tunnel Gateway 的 events SSE 连接；
    - 通过 req_id 将 RESULT/CHUNK 分发给等待者；
    - tool.* 事件写入 WorkflowRunEvent（DB + Redis），供前端 SSE 订阅回放。
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._waiters: dict[str, _Waiter] = {}
        self._lock = asyncio.Lock()

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running():
            return
        self._task = asyncio.create_task(self._run_loop(), name="bridge-stream-dispatcher")

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except Exception:
            pass

    async def register(self, meta: WorkflowInvocationMeta) -> asyncio.Future[dict[str, Any]]:
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        async with self._lock:
            self._waiters[meta.req_id] = _Waiter(meta=meta, future=future)
        return future

    async def abort(self, *, req_id: str, reason: str = "aborted") -> None:
        async with self._lock:
            waiter = self._waiters.pop(req_id, None)
        if waiter is None:
            return
        if not waiter.future.done():
            waiter.future.set_exception(RuntimeError(reason))

    async def _emit(self, meta: WorkflowInvocationMeta, event_type: str, payload: dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            # best-effort 更新 run 活动时间戳，便于“启动清洗”判断是否 stale
            run = db.get(WorkflowRun, _as_uuid(meta.run_id))
            if run is not None:
                run.last_activity_at = _utc_now()
                db.add(run)

            ev = append_workflow_run_event(
                db,
                run_id=_as_uuid(meta.run_id),
                event_type=event_type,
                payload=payload,
            )
            created_at_iso = None
            try:
                created_at_iso = ev.created_at.isoformat() if getattr(ev, "created_at", None) is not None else None
            except Exception:
                created_at_iso = None
            envelope = build_workflow_run_event_envelope(
                run_id=meta.run_id,
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
        publish_workflow_run_event_best_effort(redis, run_id=meta.run_id, envelope=envelope)

    async def _flush_logs(self, waiter: _Waiter, *, force: bool = False) -> None:
        now = time.monotonic()
        if not waiter.log_buffer:
            return
        if not force:
            if len(waiter.log_buffer) < 2048 and (now - waiter.last_flush_at) < 0.5:
                return
        chunk = waiter.log_buffer
        waiter.log_buffer = ""
        waiter.last_flush_at = now

        await self._emit(
            waiter.meta,
            "tool.log",
            {
                "type": "tool.log",
                "run_id": waiter.meta.run_id,
                "step_id": waiter.meta.step_id,
                "req_id": waiter.meta.req_id,
                "agent_id": waiter.meta.agent_id,
                "tool_name": waiter.meta.tool_name,
                "attempt_index": waiter.meta.attempt_index,
                "channel": "stdout",
                "data": chunk,
                "dropped_bytes": int(waiter.dropped_bytes or 0),
                "dropped_lines": int(waiter.dropped_lines or 0),
            },
        )
        await self._update_log_preview(waiter.meta, chunk)

    async def _run_loop(self) -> None:
        gateway = BridgeGatewayClient()
        backoff = 0.8
        while True:
            try:
                async for msg in iter_sse_events(gateway.stream_events()):
                    if msg.event != "bridge":
                        continue
                    try:
                        env = json.loads(msg.data)
                    except Exception:
                        continue
                    if not isinstance(env, dict):
                        continue

                    env_type = str(env.get("type") or "").strip()
                    req_id = str(env.get("req_id") or "").strip()
                    if not req_id:
                        continue

                    async with self._lock:
                        waiter = self._waiters.get(req_id)
                    if waiter is None:
                        continue

                    payload = env.get("payload") if isinstance(env.get("payload"), dict) else {}

                    if env_type == "INVOKE_ACK":
                        accepted = bool(payload.get("accepted", True))
                        if not accepted:
                            # 直接转为失败结果（保持 tool_loop 风格的状态字段）
                            await self._emit(
                                waiter.meta,
                                "tool.result",
                                {
                                    "type": "tool.result",
                                    "run_id": waiter.meta.run_id,
                                    "step_id": waiter.meta.step_id,
                                    "req_id": waiter.meta.req_id,
                                    "agent_id": waiter.meta.agent_id,
                                    "tool_name": waiter.meta.tool_name,
                                    "attempt_index": waiter.meta.attempt_index,
                                    "state": "failed",
                                    "duration_ms": int(max(0, (time.monotonic() - waiter.created_at) * 1000)),
                                    "ok": False,
                                    "canceled": False,
                                    "exit_code": 0,
                                    "error": {"code": "rejected", "message": str(payload.get("reason") or "rejected")},
                                    "result_preview": None,
                                },
                            )
                            if not waiter.future.done():
                                waiter.future.set_result({"ok": False, "error": {"code": "rejected"}})
                            async with self._lock:
                                self._waiters.pop(req_id, None)
                        continue

                    if env_type == "CHUNK":
                        data = str(payload.get("data") or "")
                        waiter.dropped_bytes = int(payload.get("dropped_bytes") or 0)
                        waiter.dropped_lines = int(payload.get("dropped_lines") or 0)
                        if data:
                            waiter.log_buffer += data
                            await self._flush_logs(waiter, force=False)
                        continue

                    if env_type == "RESULT":
                        await self._flush_logs(waiter, force=True)
                        ok = bool(payload.get("ok", False))
                        canceled = bool(payload.get("canceled", False))
                        exit_code = int(payload.get("exit_code") or 0)
                        error = payload.get("error")
                        error_code = None
                        if isinstance(error, dict):
                            error_code = str(error.get("code") or "").strip() or None
                        if ok:
                            state = "done"
                        elif canceled:
                            state = "canceled"
                        elif error_code == "invoke_timeout":
                            state = "timeout"
                        else:
                            state = "failed"

                        result_preview = None
                        try:
                            if payload.get("result_json") is not None:
                                import json

                                result_preview = json.dumps(payload.get("result_json"), ensure_ascii=False)[:800]
                            elif isinstance(error, dict):
                                result_preview = str(error.get("message") or error.get("code") or "")[:800] or None
                        except Exception:
                            result_preview = None

                        await self._emit(
                            waiter.meta,
                            "tool.result",
                            {
                                "type": "tool.result",
                                "run_id": waiter.meta.run_id,
                                "step_id": waiter.meta.step_id,
                                "req_id": waiter.meta.req_id,
                                "agent_id": waiter.meta.agent_id,
                                "tool_name": waiter.meta.tool_name,
                                "attempt_index": waiter.meta.attempt_index,
                                "state": state,
                                "duration_ms": int(max(0, (time.monotonic() - waiter.created_at) * 1000)),
                                "ok": ok,
                                "canceled": canceled,
                                "exit_code": exit_code,
                                "error": error,
                                "result_preview": result_preview,
                            },
                        )

                        if not waiter.future.done():
                            waiter.future.set_result(payload)
                        async with self._lock:
                            self._waiters.pop(req_id, None)
                        continue

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BridgeStreamDispatcher: gateway stream error, retrying...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.6, 5.0)

    async def _update_log_preview(self, meta: WorkflowInvocationMeta, chunk: str) -> None:
        if not chunk:
            return
        db = SessionLocal()
        try:
            run = db.get(WorkflowRun, _as_uuid(meta.run_id))
            if run is None:
                return
            steps_state = run.steps_state if isinstance(run.steps_state, dict) else {}
            step_entry = steps_state.get(meta.step_id)
            if not isinstance(step_entry, dict):
                return
            attempts = step_entry.get("attempts")
            if not isinstance(attempts, list) or meta.attempt_index >= len(attempts):
                return
            attempt = attempts[meta.attempt_index]
            if not isinstance(attempt, dict):
                return
            existing = str(attempt.get("log_preview") or "")
            attempt["log_preview"] = _append_preview(existing, chunk)
            run.steps_state = steps_state
            run.last_activity_at = _utc_now()
            db.add(run)
            db.commit()
        finally:
            db.close()


def _as_uuid(value: str):
    from uuid import UUID

    return UUID(str(value))


def _utc_now():
    from datetime import UTC, datetime

    return datetime.now(UTC)


def _append_preview(existing: str, addition: str, *, limit: int = 8000) -> str:
    if not addition:
        return existing
    merged = (existing or "") + addition
    if len(merged) <= limit:
        return merged
    return merged[-limit:]


__all__ = ["BridgeStreamDispatcher", "WorkflowInvocationMeta"]
