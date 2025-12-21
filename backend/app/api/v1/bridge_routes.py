from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.errors import bad_request, not_found, service_unavailable
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.services.bridge_agent_token_service import (
    create_bridge_agent_token,
    generate_agent_id,
    normalize_agent_id,
    validate_agent_id,
)
from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.sse_parser import iter_sse_events

router = APIRouter(
    prefix="/v1/bridge",
    tags=["bridge"],
    dependencies=[Depends(require_jwt_token)],
)

def _bridge_request_failed_details(exc: httpx.RequestError) -> dict[str, Any]:
    return {
        "code": "bridge_gateway_error",
        "reason": exc.__class__.__name__,
        "message": str(exc),
    }


def _bridge_service_unavailable(exc: httpx.RequestError) -> HTTPException:
    return service_unavailable(
        "Bridge Gateway 不可用",
        details=_bridge_request_failed_details(exc),
    )


def _maybe_agent_offline(exc: httpx.HTTPStatusError, *, agent_id: str) -> HTTPException | None:
    if exc.response is None or exc.response.status_code != 404:
        return None
    try:
        body = exc.response.json()
    except Exception:
        return None
    if isinstance(body, dict) and body.get("error") == "agent_offline":
        return not_found("Agent 离线", details={"code": "agent_offline", "agent_id": agent_id})
    return None


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    client = BridgeGatewayClient()
    try:
        return await client.list_agents()
    except httpx.RequestError as exc:
        raise _bridge_service_unavailable(exc)
    except httpx.HTTPStatusError as exc:
        raise service_unavailable(
            "Bridge Gateway 调用失败",
            details={
                "code": "bridge_gateway_error",
                "status_code": exc.response.status_code if exc.response else None,
            },
        )


@router.get("/agents/{agent_id}/tools")
async def list_agent_tools(agent_id: str) -> dict[str, Any]:
    client = BridgeGatewayClient()
    try:
        return await client.list_tools(agent_id)
    except httpx.RequestError as exc:
        raise _bridge_service_unavailable(exc)
    except httpx.HTTPStatusError as exc:
        offline = _maybe_agent_offline(exc, agent_id=agent_id)
        if offline is not None:
            raise offline
        raise service_unavailable(
            "Bridge Gateway 调用失败",
            details={
                "code": "bridge_gateway_error",
                "status_code": exc.response.status_code if exc.response else None,
            },
        )

@router.post("/agent-token")
async def issue_agent_token(
    payload: dict[str, Any],
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict[str, Any]:
    """
    为用户生成 Bridge Agent 连接 Tunnel Gateway 使用的 token（JWT HS256）。

    说明：
    - token 仅用于 Agent -> Gateway 的 AUTH（不包含用户 MCP 密钥）。
    - token 不落库；如需吊销/轮换，可后续引入 DB/Redis revocation。
    """
    requested = payload.get("agent_id")
    agent_id = normalize_agent_id(str(requested) if requested is not None else None)
    if not agent_id:
        agent_id = generate_agent_id()
    try:
        validate_agent_id(agent_id)
    except ValueError as exc:
        raise bad_request("agent_id 不合法", details={"code": "invalid_agent_id", "message": str(exc)})

    token, expires_at = create_bridge_agent_token(user_id=str(current_user.id), agent_id=agent_id)
    return {"agent_id": agent_id, "token": token, "expires_at": expires_at.isoformat()}


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
    if not agent_id:
        raise bad_request("缺少 agent_id")
    if not tool_name:
        raise bad_request("缺少 tool_name")

    try:
        return await client.invoke(
            req_id=req_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            timeout_ms=timeout_ms,
            stream=stream,
        )
    except httpx.RequestError as exc:
        raise _bridge_service_unavailable(exc)
    except httpx.HTTPStatusError as exc:
        offline = _maybe_agent_offline(exc, agent_id=agent_id)
        if offline is not None:
            raise offline
        raise service_unavailable(
            "Bridge Gateway 调用失败",
            details={"code": "bridge_gateway_error", "status_code": exc.response.status_code if exc.response else None},
        )


@router.post("/cancel")
async def cancel_tool(payload: dict[str, Any]) -> dict[str, Any]:
    req_id = str(payload.get("req_id") or "").strip()
    agent_id = str(payload.get("agent_id") or "").strip()
    reason = str(payload.get("reason") or "user_cancel").strip()
    client = BridgeGatewayClient()
    if not req_id:
        raise bad_request("缺少 req_id")
    if not agent_id:
        raise bad_request("缺少 agent_id")
    try:
        return await client.cancel(req_id=req_id, agent_id=agent_id, reason=reason)
    except httpx.RequestError as exc:
        raise _bridge_service_unavailable(exc)
    except httpx.HTTPStatusError as exc:
        offline = _maybe_agent_offline(exc, agent_id=agent_id)
        if offline is not None:
            raise offline
        raise service_unavailable(
            "Bridge Gateway 调用失败",
            details={"code": "bridge_gateway_error", "status_code": exc.response.status_code if exc.response else None},
        )


@router.get("/events")
async def bridge_events() -> StreamingResponse:
    """
    代理 Tunnel Gateway 的 SSE 事件流到前端（原样透传）。
    """
    client = BridgeGatewayClient()
    return StreamingResponse(client.stream_events(), media_type="text/event-stream")

@router.get("/tool-events")
async def bridge_tool_events() -> StreamingResponse:
    """
    将 Gateway 的原始 Envelope 流，转换为前端约定的 tool_* SSE 事件。

    事件：
    - tool_status: sent|acked|running|canceled|done|error
    - tool_log: stdout/stderr + dropped 计数
    - tool_result: 终态结果（与 RESULT payload 同构）

    说明：该流用于 UI 展示；并不改变 Gateway/Agent 的底层协议。
    """
    gateway = BridgeGatewayClient()

    async def gen():
        async for msg in iter_sse_events(gateway.stream_events()):
            if msg.event == "ready":
                yield "event: ready\ndata: {}\n\n"
                continue
            if msg.event != "bridge":
                continue
            try:
                env = json.loads(msg.data)
            except Exception:
                continue
            if not isinstance(env, dict):
                continue

            env_type = str(env.get("type") or "").strip()
            agent_id = str(env.get("agent_id") or "").strip()
            req_id = str(env.get("req_id") or "").strip()
            payload = env.get("payload") if isinstance(env.get("payload"), dict) else {}

            def _emit(event: str, data: dict[str, Any]) -> str:
                return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            if env_type == "INVOKE_ACK":
                accepted = bool(payload.get("accepted", True))
                if accepted:
                    yield _emit(
                        "tool_status",
                        {"req_id": req_id, "agent_id": agent_id, "state": "acked", "message": ""},
                    )
                else:
                    yield _emit(
                        "tool_status",
                        {
                            "req_id": req_id,
                            "agent_id": agent_id,
                            "state": "error",
                            "message": str(payload.get("reason") or "rejected"),
                        },
                    )
                continue

            if env_type == "CHUNK":
                yield _emit(
                    "tool_log",
                    {
                        "req_id": req_id,
                        "agent_id": agent_id,
                        "channel": str(payload.get("channel") or "stdout"),
                        "data": str(payload.get("data") or ""),
                        "dropped_bytes": int(payload.get("dropped_bytes") or 0),
                        "dropped_lines": int(payload.get("dropped_lines") or 0),
                    },
                )
                continue

            if env_type == "RESULT":
                yield _emit(
                    "tool_result",
                    {
                        "req_id": req_id,
                        "agent_id": agent_id,
                        "ok": bool(payload.get("ok", False)),
                        "exit_code": int(payload.get("exit_code") or 0),
                        "canceled": bool(payload.get("canceled", False)),
                        "result_json": payload.get("result_json"),
                        "error": payload.get("error"),
                    },
                )
                yield _emit(
                    "tool_status",
                    {"req_id": req_id, "agent_id": agent_id, "state": "done", "message": ""},
                )
                continue

            if env_type == "CANCEL_ACK":
                will_cancel = bool(payload.get("will_cancel", False))
                yield _emit(
                    "tool_status",
                    {
                        "req_id": req_id,
                        "agent_id": agent_id,
                        "state": "canceled" if will_cancel else "done",
                        "message": str(payload.get("reason") or ""),
                    },
                )
                continue

    return StreamingResponse(gen(), media_type="text/event-stream")


__all__ = ["router"]
