from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.settings import settings


class BridgeGatewayClient:
    """
    与云端 Tunnel Gateway（Go）通信的内部客户端。

    说明：
    - 这是云端内部组件之间的调用（Backend -> Tunnel Gateway），不涉及用户本地 Redis。
    - MVP 阶段 Tunnel Gateway 可单实例运行（无 Redis）；后续 HA 时可由 Gateway 自行接入 Redis 做路由。
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        internal_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = (base_url or settings.bridge_gateway_url).rstrip("/")
        self._internal_token = (internal_token or settings.bridge_gateway_internal_token).strip()
        self._timeout = float(timeout)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._internal_token:
            headers["X-Internal-Token"] = self._internal_token
        return headers

    async def list_agents(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get("/internal/bridge/agents", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def list_tools(self, agent_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get(
                f"/internal/bridge/agents/{agent_id}/tools",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def invoke(
        self,
        *,
        req_id: str,
        agent_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
        timeout_ms: int = 60000,
        stream: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "req_id": req_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "arguments": arguments or {},
            "timeout_ms": int(timeout_ms),
            "stream": bool(stream),
        }
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.post(
                "/internal/bridge/invoke",
                headers={**self._headers(), "Content-Type": "application/json"},
                content=json.dumps(payload, ensure_ascii=False),
            )
            resp.raise_for_status()
            return resp.json()

    async def cancel(self, *, req_id: str, agent_id: str, reason: str = "user_cancel") -> dict[str, Any]:
        payload = {"req_id": req_id, "agent_id": agent_id, "reason": reason}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.post(
                "/internal/bridge/cancel",
                headers={**self._headers(), "Content-Type": "application/json"},
                content=json.dumps(payload, ensure_ascii=False),
            )
            resp.raise_for_status()
            return resp.json()

    async def stream_events(self) -> AsyncIterator[bytes]:
        """
        代理 Tunnel Gateway 的 SSE 事件流（原样 bytes 透传）。
        """
        async with httpx.AsyncClient(base_url=self._base_url, timeout=None) as client:
            async with client.stream(
                "GET",
                settings.bridge_gateway_events_path,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_raw():
                    if not chunk:
                        continue
                    yield chunk

