from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.auth import AuthenticatedAPIKey
from app.db.session import SessionLocal
from app.http_client import CurlCffiClient
from app.jwt_auth import AuthenticatedUser
from app.logging_config import logger
from app.models import APIKey, AssistantPreset, Conversation, Message, Run, User
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.repositories.chat_repository import persist_run, refresh_run
from app.repositories.run_event_repository import append_run_event
from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.bridge_tool_runner import bridge_tools_by_agent_to_openai_tools, invoke_bridge_tool_and_wait
from app.services.chat_history_service import (
    create_assistant_message_after_user,
    finalize_assistant_message_after_user_sequence,
)
from app.services.chat_run_service import execute_run_non_stream
from app.services.conversation_summary_service import maybe_update_conversation_summary
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
    resolve_project_context,
)
from app.services.run_event_bus import build_run_event_envelope, publish_run_event_best_effort
from app.services.run_cancel_service import is_run_canceled
from app.services.tool_loop_runner import ToolLoopRunner, split_text_into_deltas
from app.services.eval_service import execute_run_stream
from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


def _to_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=bool(getattr(user, "is_superuser", False)),
        is_active=bool(getattr(user, "is_active", True)),
        display_name=getattr(user, "display_name", None),
        avatar=None,
    )


def _to_authenticated_api_key(db, *, api_key: APIKey) -> AuthenticatedAPIKey:
    user = db.execute(select(User).where(User.id == api_key.user_id)).scalars().first()
    if user is None:
        raise RuntimeError("api_key user not found")
    return AuthenticatedAPIKey(
        id=UUID(str(api_key.id)),
        user_id=UUID(str(user.id)),
        user_username=user.username,
        is_superuser=bool(user.is_superuser),
        name=api_key.name,
        is_active=bool(api_key.is_active),
        disabled_reason=api_key.disabled_reason,
        has_provider_restrictions=bool(api_key.has_provider_restrictions),
        allowed_provider_ids=list(api_key.allowed_provider_ids),
    )


def _extract_tool_invocations(run: Run) -> list[dict[str, Any]]:
    try:
        payload = getattr(run, "response_payload", None)
        if isinstance(payload, dict):
            bridge = payload.get("bridge")
            if isinstance(bridge, dict) and isinstance(bridge.get("tool_invocations"), list):
                return [it for it in bridge["tool_invocations"] if isinstance(it, dict)]
    except Exception:
        pass
    return []


def _run_to_summary(run: Run) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "requested_logical_model": run.requested_logical_model,
        "status": run.status,
        "output_preview": run.output_preview,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
        "tool_invocations": _extract_tool_invocations(run),
    }


def _append_run_event_and_publish_best_effort(
    db,
    *,
    redis: Redis | None,
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> int | None:
    try:
        row = append_run_event(db, run_id=run_id, event_type=event_type, payload=payload)
        created_at_iso = None
        try:
            created_at_iso = row.created_at.isoformat() if getattr(row, "created_at", None) is not None else None
        except Exception:
            created_at_iso = None
        publish_run_event_best_effort(
            redis,
            run_id=run_id,
            envelope=build_run_event_envelope(
                run_id=run_id,
                seq=int(getattr(row, "seq", 0) or 0),
                event_type=str(getattr(row, "event_type", event_type) or event_type),
                created_at_iso=created_at_iso,
                payload=payload,
            ),
        )
        return int(getattr(row, "seq", 0) or 0)
    except Exception:  # pragma: no cover - best-effort only
        logger.debug("chat_run task: append_run_event failed (run_id=%s type=%s)", run_id, event_type, exc_info=True)
        return None


async def _build_tool_name_map_for_payload(
    *,
    payload: dict[str, Any],
    effective_bridge_agent_ids: list[str],
) -> dict[str, tuple[str, str]]:
    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools:
        return {}

    allowed_openai_names: set[str] = set()
    for t in tools:
        if not isinstance(t, dict):
            continue
        fn = t.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str) and fn["name"].strip():
            allowed_openai_names.add(fn["name"].strip())

    if not allowed_openai_names:
        return {}

    if len(effective_bridge_agent_ids) <= 1:
        return {}

    bridge_tools_by_agent: dict[str, list[dict[str, Any]]] = {}
    bridge = BridgeGatewayClient()
    for aid in effective_bridge_agent_ids:
        try:
            tools_resp = await bridge.list_tools(aid)
        except Exception:
            continue
        if isinstance(tools_resp, dict) and isinstance(tools_resp.get("tools"), list):
            bridge_tools_by_agent[aid] = [t for t in tools_resp["tools"] if isinstance(t, dict)]

    _, full_map = bridge_tools_by_agent_to_openai_tools(
        bridge_tools_by_agent=bridge_tools_by_agent,
    )
    return {k: v for k, v in full_map.items() if k in allowed_openai_names}


async def execute_chat_run(
    *,
    run_id: str,
    assistant_message_id: str | None = None,
    effective_bridge_agent_ids: list[str] | None = None,
    streaming: bool = False,
) -> str:
    """
    执行一个 chat run（在 Celery worker 中运行）：
    - LLM 调用与 tool loop 在 worker 内完成；
    - 过程事件写入 RunEvent（DB 真相）并同步发布到 Redis 热通道；
    - streaming=True 时，会持续写入 message.delta 事件（供 SSE 转发/回放）。
    """
    run_uuid = UUID(str(run_id))
    SessionFactory = SessionLocal

    redis = get_redis_client()
    try:
        with SessionFactory() as db:
            run = db.get(Run, run_uuid)
            if run is None:
                return "skipped:no_run"

            if str(run.status or "") in {"succeeded", "failed", "canceled"}:
                return "skipped:already_finished"

            user = db.execute(select(User).where(User.id == run.user_id)).scalars().first()
            if user is None:
                return "failed:no_user"
            current_user = _to_authenticated_user(user)

            message = db.get(Message, UUID(str(run.message_id)))
            if message is None:
                return "failed:no_message"

            conv = db.get(Conversation, UUID(str(message.conversation_id)))
            if conv is None:
                return "failed:no_conversation"

            assistant = db.get(AssistantPreset, UUID(str(conv.assistant_id)))
            if assistant is None:
                return "failed:no_assistant"

            ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)
            cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)
            effective_provider_ids = get_effective_provider_ids_for_user(
                db,
                user_id=UUID(str(current_user.id)),
                api_key=ctx.api_key,
                provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
            )
            auth_key = _to_authenticated_api_key(db, api_key=ctx.api_key)

            payload = dict(run.request_payload or {}) if isinstance(run.request_payload, dict) else {}
            requested_model = str(getattr(run, "requested_logical_model", "") or "").strip()

            bridge_agent_ids = list(effective_bridge_agent_ids or [])

        async with CurlCffiClient(
            timeout=settings.upstream_timeout,
            impersonate="chrome120",
            trust_env=True,
        ) as client:
            with SessionFactory() as db:
                run = db.get(Run, run_uuid)
                if run is None:
                    return "skipped:no_run"

                message = db.get(Message, UUID(str(run.message_id)))
            if message is None:
                return "failed:no_message"
            conv = db.get(Conversation, UUID(str(message.conversation_id)))
            if conv is None:
                return "failed:no_conversation"
            assistant = db.get(AssistantPreset, UUID(str(conv.assistant_id)))
            if assistant is None:
                return "failed:no_assistant"
            user_message_id = str(run.message_id)
            conversation_id = str(conv.id) if conv is not None else ""

            async def _apply_cancel_if_needed() -> bool:
                try:
                    if not await is_run_canceled(redis, run_id=run_uuid):
                        return False
                except Exception:
                    return False

                # refresh 一次，尽量避免与 cancel endpoint 重复落库
                try:
                    db.refresh(run)
                except Exception:
                    pass

                if str(run.status or "") in {"succeeded", "failed", "canceled"}:
                    return True

                run.status = "canceled"
                run.error_code = "CANCELED"
                run.error_message = "canceled"
                run.finished_at = datetime.now(UTC)
                db.add(run)
                db.commit()
                db.refresh(run)

                _append_run_event_and_publish_best_effort(
                    db,
                    redis=redis,
                    run_id=UUID(str(run.id)),
                    event_type="run.canceled",
                    payload={"type": "run.canceled", "run_id": str(run.id)},
                )
                _append_run_event_and_publish_best_effort(
                    db,
                    redis=redis,
                    run_id=UUID(str(run.id)),
                    event_type="message.failed",
                    payload={
                        "type": "message.failed",
                        "conversation_id": str(conv.id),
                        "user_message_id": str(message.id),
                        "assistant_message_id": assistant_message_id,
                        "baseline_run": _run_to_summary(run),
                        "output_text": None,
                    },
                )
                return True

            if await _apply_cancel_if_needed():
                return "canceled"

            if not streaming:
                if await _apply_cancel_if_needed():
                    return "canceled"

                if str(run.status or "") == "queued":
                    run.status = "running"
                    run.started_at = datetime.now(UTC)
                    db.add(run)
                    db.commit()
                    db.refresh(run)

                run = await execute_run_non_stream(
                    db,
                    redis=redis,
                    client=client,
                    api_key=auth_key,
                    effective_provider_ids=effective_provider_ids,
                    conversation=conv,
                    assistant=assistant,
                    user_message=message,
                    run=run,
                    requested_logical_model=requested_model,
                    payload_override=payload or None,
                )

                if run.status == "succeeded" and bridge_agent_ids and isinstance(payload.get("tools"), list) and payload["tools"]:
                    tool_name_map = await _build_tool_name_map_for_payload(
                        payload=payload,
                        effective_bridge_agent_ids=bridge_agent_ids,
                    )
                    tool_loop_provider_ids = effective_provider_ids
                    pinned_provider_id = str(getattr(run, "selected_provider_id", None) or "").strip()
                    if pinned_provider_id and pinned_provider_id in tool_loop_provider_ids:
                        tool_loop_provider_ids = {pinned_provider_id}

                    async def _invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict[str, Any]):
                        return await invoke_bridge_tool_and_wait(
                            req_id=req_id,
                            agent_id=agent_id,
                            tool_name=tool_name,
                            arguments=arguments,
                            timeout_ms=60_000,
                            result_timeout_seconds=120.0,
                        )

                    async def _cancel_tool(req_id: str, agent_id: str, reason: str) -> None:
                        bridge = BridgeGatewayClient()
                        await bridge.cancel(req_id=req_id, agent_id=agent_id, reason=reason)

                    async def _call_model(follow_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
                        from app.api.v1.chat.request_handler import RequestHandler

                        handler = RequestHandler(api_key=auth_key, db=db, redis=redis, client=client)
                        resp = await handler.handle(
                            payload=follow_payload,
                            requested_model=requested_model,
                            lookup_model_id=requested_model,
                            api_style="openai",
                            effective_provider_ids=tool_loop_provider_ids,
                            session_id=str(conv.id),
                            assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
                            billing_reason="chat_tool_loop",
                            idempotency_key=idempotency_key or None,
                        )
                        try:
                            raw = resp.body.decode("utf-8", errors="ignore")
                            parsed = json.loads(raw)
                            if isinstance(parsed, dict):
                                return parsed
                        except Exception:
                            return None
                        return None

                    runner = ToolLoopRunner(
                        invoke_tool=_invoke_tool,
                        call_model=_call_model,
                        cancel_tool=_cancel_tool,
                        event_sink=lambda et, p: _append_run_event_and_publish_best_effort(
                            db,
                            redis=redis,
                            run_id=UUID(str(run.id)),
                            event_type=et,
                            payload=p,
                        ),
                    )

                    result = await runner.run(
                        conversation_id=conversation_id,
                        run_id=str(run.id),
                        base_payload=payload,
                        first_response_payload=getattr(run, "response_payload", None),
                        effective_bridge_agent_ids=bridge_agent_ids,
                        tool_name_map=tool_name_map,
                        user_message_id=user_message_id,
                        idempotency_prefix=f"chat:{run.id}:tool_loop",
                    )

                    if result.did_run:
                        output_text = result.output_text
                        if result.error_code:
                            run.status = "failed"
                            run.error_code = result.error_code
                            run.error_message = result.error_message
                        elif output_text and output_text.strip():
                            run.output_text = output_text
                            run.output_preview = output_text.strip()[:380].rstrip()
                        else:
                            run.status = "failed"
                            run.error_code = "TOOL_LOOP_FAILED"
                            run.error_message = "tool loop finished without assistant content"

                        run.response_payload = {
                            "bridge": {
                                "agent_ids": bridge_agent_ids,
                                "tool_invocations": result.tool_invocations,
                            },
                            "first_response": result.first_response_payload,
                            "final_response": result.final_response_payload,
                        }
                        run = persist_run(db, run)

                assistant_msg: Message | None = None
                if run.status == "succeeded" and run.output_text:
                    assistant_msg = create_assistant_message_after_user(
                        db,
                        conversation_id=UUID(str(conv.id)),
                        user_sequence=int(message.sequence or 0),
                        content_text=run.output_text,
                    )
                    try:
                        await maybe_update_conversation_summary(
                            db,
                            redis=redis,
                            client=client,
                            api_key=auth_key,
                            effective_provider_ids=effective_provider_ids,
                            conversation_id=UUID(str(conv.id)),
                            assistant_id=UUID(str(assistant.id)),
                            requested_logical_model=requested_model,
                            new_until_sequence=int(getattr(assistant_msg, "sequence", 0) or 0),
                        )
                    except Exception:  # pragma: no cover - best-effort only
                        logger.debug(
                            "chat_run: conversation summary update failed (conversation_id=%s)",
                            str(conv.id),
                            exc_info=True,
                        )

                _append_run_event_and_publish_best_effort(
                    db,
                    redis=redis,
                    run_id=UUID(str(run.id)),
                    event_type="message.completed" if run.status == "succeeded" else "message.failed",
                    payload={
                        "type": "message.completed" if run.status == "succeeded" else "message.failed",
                        "conversation_id": str(conv.id),
                        "user_message_id": str(message.id),
                        "assistant_message_id": str(assistant_msg.id) if assistant_msg is not None else None,
                        "baseline_run": _run_to_summary(run),
                        "output_text": run.output_text if run.status == "succeeded" else None,
                    },
                )
                return "done"

            # --- streaming mode ---
            parts: list[str] = []
            errored = False
            first_response_started_at = time.perf_counter()

            async for item in execute_run_stream(
                db,
                redis=redis,
                client=client,
                api_key=auth_key,
                effective_provider_ids=effective_provider_ids,
                conversation=conv,
                assistant=assistant,
                user_message=message,
                run=run,
                requested_logical_model=requested_model,
                payload_override=payload or None,
            ):
                if await _apply_cancel_if_needed():
                    return "canceled"
                if not isinstance(item, dict):
                    continue
                itype = str(item.get("type") or "")

                if itype == "run.delta":
                    delta = item.get("delta")
                    if isinstance(delta, str) and delta:
                        parts.append(delta)
                        _append_run_event_and_publish_best_effort(
                            db,
                            redis=redis,
                            run_id=UUID(str(run.id)),
                            event_type="message.delta",
                            payload={
                                "type": "message.delta",
                                "conversation_id": str(conv.id),
                                "assistant_message_id": assistant_message_id,
                                "run_id": str(run.id),
                                "delta": delta,
                            },
                        )
                elif itype == "run.error":
                    errored = True
                    _append_run_event_and_publish_best_effort(
                        db,
                        redis=redis,
                        run_id=UUID(str(run.id)),
                        event_type="message.error",
                        payload={
                            "type": "message.error",
                            "conversation_id": str(conv.id),
                            "assistant_message_id": assistant_message_id,
                            "run_id": str(run.id),
                            "error_code": item.get("error_code"),
                            "error": item.get("error"),
                        },
                    )
                    break

            logger.info(
                "chat_run task stream finished: run_id=%s chunks=%d errored=%s elapsed_ms=%.2f",
                str(run.id),
                len(parts),
                errored,
                (time.perf_counter() - first_response_started_at) * 1000,
            )
            run = refresh_run(db, run)

            if run.status == "succeeded" and bridge_agent_ids and isinstance(payload.get("tools"), list) and payload["tools"]:
                tool_name_map = await _build_tool_name_map_for_payload(
                    payload=payload,
                    effective_bridge_agent_ids=bridge_agent_ids,
                )
                tool_loop_provider_ids = effective_provider_ids
                pinned_provider_id = str(getattr(run, "selected_provider_id", None) or "").strip()
                if pinned_provider_id and pinned_provider_id in tool_loop_provider_ids:
                    tool_loop_provider_ids = {pinned_provider_id}

                async def _invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict[str, Any]):
                    return await invoke_bridge_tool_and_wait(
                        req_id=req_id,
                        agent_id=agent_id,
                        tool_name=tool_name,
                        arguments=arguments,
                        timeout_ms=60_000,
                        result_timeout_seconds=120.0,
                    )

                async def _cancel_tool(req_id: str, agent_id: str, reason: str) -> None:
                    bridge = BridgeGatewayClient()
                    await bridge.cancel(req_id=req_id, agent_id=agent_id, reason=reason)

                async def _call_model(follow_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
                    from app.api.v1.chat.request_handler import RequestHandler

                    handler = RequestHandler(api_key=auth_key, db=db, redis=redis, client=client)
                    resp = await handler.handle(
                        payload=follow_payload,
                        requested_model=requested_model,
                        lookup_model_id=requested_model,
                        api_style="openai",
                        effective_provider_ids=tool_loop_provider_ids,
                        session_id=str(conv.id),
                        assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
                        billing_reason="chat_tool_loop",
                        idempotency_key=idempotency_key or None,
                    )
                    try:
                        raw = resp.body.decode("utf-8", errors="ignore")
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        return None
                    return None

                runner = ToolLoopRunner(
                    invoke_tool=_invoke_tool,
                    call_model=_call_model,
                    cancel_tool=_cancel_tool,
                    event_sink=lambda et, p: _append_run_event_and_publish_best_effort(
                        db,
                        redis=redis,
                        run_id=UUID(str(run.id)),
                        event_type=et,
                        payload=p,
                    ),
                )

                result = await runner.run(
                    conversation_id=str(conv.id),
                    run_id=str(run.id),
                    base_payload=payload,
                    first_response_payload=getattr(run, "response_payload", None),
                    effective_bridge_agent_ids=bridge_agent_ids,
                    tool_name_map=tool_name_map,
                    assistant_message_id=assistant_message_id,
                    user_message_id=str(message.id),
                    idempotency_prefix=f"chat:{run.id}:tool_loop",
                )

                if result.did_run:
                    delta_text = result.output_text
                    if result.error_code:
                        run.status = "failed"
                        run.error_code = result.error_code
                        run.error_message = result.error_message
                        delta_text = None
                    elif delta_text and delta_text.strip():
                        run.output_text = delta_text
                        run.output_preview = delta_text.strip()[:380].rstrip()
                    else:
                        run.status = "failed"
                        run.error_code = "TOOL_LOOP_FAILED"
                        run.error_message = "tool loop finished without assistant content"
                        delta_text = None

                    run.response_payload = {
                        "bridge": {
                            "agent_ids": bridge_agent_ids,
                            "tool_invocations": result.tool_invocations,
                        },
                        "first_response": result.first_response_payload,
                        "final_response": result.final_response_payload,
                    }
                    run = persist_run(db, run)

                    if delta_text:
                        parts = []
                        chunks = split_text_into_deltas(delta_text)
                        # 轻量节奏控制：把“工具后续”切成多段 delta，避免一次性灌入导致前端看起来不流式。
                        pace_s = 0.0
                        if len(chunks) > 1:
                            pace_s = min(0.05, 0.9 / float(len(chunks)))
                        for idx, chunk in enumerate(chunks):
                            parts.append(chunk)
                            _append_run_event_and_publish_best_effort(
                                db,
                                redis=redis,
                                run_id=UUID(str(run.id)),
                                event_type="message.delta",
                                payload={
                                    "type": "message.delta",
                                    "conversation_id": str(conv.id),
                                    "assistant_message_id": assistant_message_id,
                                    "run_id": str(run.id),
                                    "delta": chunk,
                                },
                            )
                            if pace_s and idx < len(chunks) - 1:
                                await asyncio.sleep(pace_s)

            if not errored and run.status == "succeeded" and run.output_text and assistant_message_id:
                finalize_assistant_message_after_user_sequence(
                    db,
                    conversation_id=UUID(str(conv.id)),
                    user_sequence=int(message.sequence or 0),
                    content_text=run.output_text,
                )
                try:
                    await maybe_update_conversation_summary(
                        db,
                        redis=redis,
                        client=client,
                        api_key=auth_key,
                        effective_provider_ids=effective_provider_ids,
                        conversation_id=UUID(str(conv.id)),
                        assistant_id=UUID(str(assistant.id)),
                        requested_logical_model=requested_model,
                        new_until_sequence=int(message.sequence or 0) + 1,
                    )
                except Exception:  # pragma: no cover - best-effort only
                    logger.debug(
                        "chat_run: conversation summary update failed (conversation_id=%s)",
                        str(conv.id),
                        exc_info=True,
                    )

            _append_run_event_and_publish_best_effort(
                db,
                redis=redis,
                run_id=UUID(str(run.id)),
                event_type="message.completed" if run.status == "succeeded" else "message.failed",
                payload={
                    "type": "message.completed" if run.status == "succeeded" else "message.failed",
                    "conversation_id": str(conv.id),
                    "assistant_message_id": assistant_message_id,
                    "baseline_run": _run_to_summary(run),
                    "output_text": "".join(parts) if parts else None,
                },
            )
            return "done"
    finally:
        await close_redis_client_for_current_loop()


@shared_task(name="tasks.execute_chat_run")
def execute_chat_run_task(
    run_id: str,
    assistant_message_id: str | None = None,
    effective_bridge_agent_ids: list[str] | None = None,
    streaming: bool = False,
) -> str:
    try:
        return asyncio.run(
            execute_chat_run(
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                effective_bridge_agent_ids=effective_bridge_agent_ids,
                streaming=bool(streaming),
            )
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("chat_run task failed: %s", exc)
        return "failed"


__all__ = ["execute_chat_run", "execute_chat_run_task"]
