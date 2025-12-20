from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.jwt_auth import require_jwt_token
from app.services.bridge_gateway_client import BridgeGatewayClient

router = APIRouter(
    prefix="/v1/bridge",
    tags=["bridge"],
    dependencies=[Depends(require_jwt_token)],
)


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    client = BridgeGatewayClient()
    return await client.list_agents()


@router.get("/agents/{agent_id}/tools")
async def list_agent_tools(agent_id: str) -> dict[str, Any]:
    client = BridgeGatewayClient()
    return await client.list_tools(agent_id)


@router.post("/invoke")
async def invoke_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """
    MVP：直接透传到 Tunnel Gateway。

    说明：
    - 未来需要把 agent_id 与用户身份做绑定校验（多租户安全），此处先按内部演示打通链路。
    """
    req_id = str(payload.get("req_id") or "").strip() or uuid.uuid4().hex
    agent_id = str(payload.get("agent_id") or "").strip()
    tool_name = str(payload.get("tool_name") or "").strip()
    arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
    timeout_ms = int(payload.get("timeout_ms") or 60000)
    stream = bool(payload.get("stream", True))

    client = BridgeGatewayClient()
    return await client.invoke(
        req_id=req_id,
        agent_id=agent_id,
        tool_name=tool_name,
        arguments=arguments,
        timeout_ms=timeout_ms,
        stream=stream,
    )


@router.post("/cancel")
async def cancel_tool(payload: dict[str, Any]) -> dict[str, Any]:
    req_id = str(payload.get("req_id") or "").strip()
    agent_id = str(payload.get("agent_id") or "").strip()
    reason = str(payload.get("reason") or "user_cancel").strip()
    client = BridgeGatewayClient()
    return await client.cancel(req_id=req_id, agent_id=agent_id, reason=reason)


@router.get("/events")
async def bridge_events() -> StreamingResponse:
    """
    代理 Tunnel Gateway 的 SSE 事件流到前端（原样透传）。
    """
    client = BridgeGatewayClient()
    return StreamingResponse(client.stream_events(), media_type="text/event-stream")


__all__ = ["router"]

