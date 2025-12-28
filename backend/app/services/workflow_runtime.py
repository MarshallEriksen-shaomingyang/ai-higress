from __future__ import annotations

import asyncio
import os
from uuid import UUID

from app.logging_config import logger
from app.services.workflow_bridge_dispatcher import BridgeStreamDispatcher
from app.services.workflow_engine import WorkflowEngine


class WorkflowRuntime:
    def __init__(self) -> None:
        self.dispatcher = BridgeStreamDispatcher()
        self.engine = WorkflowEngine(self.dispatcher)
        self._started = False
        self._lock = asyncio.Lock()

    async def ensure_started(self) -> None:
        if self._started:
            return
        async with self._lock:
            if self._started:
                return
            if os.getenv("PYTEST_CURRENT_TEST"):
                # 测试环境默认不启动常驻 SSE 连接（测试可按需 override）
                self._started = True
                return
            await self.dispatcher.start()
            self._started = True

    async def shutdown(self) -> None:
        try:
            await self.dispatcher.stop()
        except Exception:
            logger.exception("WorkflowRuntime shutdown error")

    async def spawn_run(self, run_id: UUID) -> None:
        await self.ensure_started()
        await self.engine.spawn(run_id)

    async def cancel_local(self, run_id: UUID) -> None:
        await self.engine.cancel_local(run_id)


_runtime: WorkflowRuntime | None = None


def get_workflow_runtime() -> WorkflowRuntime:
    global _runtime
    if _runtime is None:
        _runtime = WorkflowRuntime()
    return _runtime


__all__ = ["WorkflowRuntime", "get_workflow_runtime"]

