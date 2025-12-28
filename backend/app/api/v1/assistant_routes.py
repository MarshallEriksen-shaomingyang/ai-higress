from __future__ import annotations

import json
import os
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from app.deps import get_db, get_http_client, get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Message
from app.repositories.run_event_repository import append_run_event, list_run_events
from app.schemas import (
    AssistantPresetCreateRequest,
    AssistantPresetListResponse,
    AssistantPresetResponse,
    AssistantPresetUpdateRequest,
    ConversationImageGenerationRequest,
    ConversationCreateRequest,
    ConversationItem,
    ConversationListResponse,
    ConversationUpdateRequest,
    MessageCreateRequest,
    MessageCreateResponse,
    MessageRegenerateRequest,
    MessageRegenerateResponse,
    MessageListResponse,
    RunDetailResponse,
    RunSummary,
)
from app.services import chat_app_service
from app.services.run_cancel_service import mark_run_canceled
from app.services.run_event_bus import build_run_event_envelope, publish_run_event_best_effort, run_event_channel
from app.services.run_event_bus import subscribe_run_events
from app.services.chat_history_service import (
    clear_conversation_messages,
    create_assistant,
    create_conversation,
    delete_assistant,
    delete_conversation,
    get_assistant,
    delete_message,
    get_run_detail,
    list_assistants,
    list_conversations,
    list_messages_with_run_summaries,
    update_assistant,
    update_conversation,
)
from app.services.image_storage_service import build_signed_image_url
from app.services.image_generation_chat_service import (
    create_image_generation_and_queue_run,
    execute_image_generation_inline,
)
from app.services.chat_history_service import finalize_assistant_image_generation_after_user_sequence

router = APIRouter(
    tags=["assistants"],
    dependencies=[Depends(require_jwt_token)],
)

def _encode_sse_event(*, event_type: str, data: Any) -> bytes:
    """
    SSE 编码：同时发送 `event:` 与 `data:`；data 中一般也包含 `type` 字段便于统一解析。
    """
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
        # 兼容 Pydantic/BaseModel、UUID、datetime 等对象（例如 baseline_run）
        serializable = jsonable_encoder(data)
        lines.append(f"data: {json.dumps(serializable, ensure_ascii=False)}")

    return ("\n".join(lines) + "\n\n").encode("utf-8")


def _assistant_to_response(obj) -> AssistantPresetResponse:
    return AssistantPresetResponse(
        assistant_id=obj.id,
        project_id=obj.api_key_id,
        name=obj.name,
        system_prompt=obj.system_prompt,
        default_logical_model=obj.default_logical_model,
        title_logical_model=getattr(obj, "title_logical_model", None),
        model_preset=obj.model_preset,
        archived_at=obj.archived_at,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _conversation_to_item(obj) -> dict:
    return {
        "conversation_id": obj.id,
        "assistant_id": obj.assistant_id,
        "project_id": obj.api_key_id,
        "title": obj.title,
        "last_activity_at": obj.last_activity_at,
        "archived_at": obj.archived_at,
        "is_pinned": obj.is_pinned,
        "last_message_content": obj.last_message_content,
        "unread_count": obj.unread_count,
        "summary_text": getattr(obj, "summary_text", None),
        "summary_until_sequence": int(getattr(obj, "summary_until_sequence", 0) or 0),
        "summary_updated_at": getattr(obj, "summary_updated_at", None),
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }


def _hydrate_image_generation_content(content: dict) -> dict:
    """
    将存储在 DB 中的 image_generation content（通常只保存 object_key）补全为带短链 url 的响应体。
    """
    if not isinstance(content, dict):
        return content
    if str(content.get("type") or "") != "image_generation":
        return content

    images = content.get("images")
    if not isinstance(images, list) or not images:
        return content

    hydrated: list[dict[str, Any]] = []
    for item in images:
        if not isinstance(item, dict):
            continue
        object_key = item.get("object_key")
        url = item.get("url")
        b64_json = item.get("b64_json")
        next_item = dict(item)
        if isinstance(object_key, str) and object_key.strip():
            next_item["url"] = build_signed_image_url(object_key.strip())
        elif isinstance(url, str) and url.strip():
            next_item["url"] = url.strip()
        elif isinstance(b64_json, str) and b64_json.strip():
            next_item["url"] = f"data:image/png;base64,{b64_json.strip()}"
        hydrated.append(next_item)

    next_content = dict(content)
    next_content["images"] = hydrated
    return next_content


def _run_to_summary(run) -> RunSummary:
    tool_invocations: list[dict[str, Any]] = []
    try:
        payload = getattr(run, "response_payload", None)
        if isinstance(payload, dict):
            bridge = payload.get("bridge")
            if isinstance(bridge, dict) and isinstance(bridge.get("tool_invocations"), list):
                tool_invocations = [it for it in bridge["tool_invocations"] if isinstance(it, dict)]
    except Exception:
        tool_invocations = []
    return RunSummary(
        run_id=run.id,
        requested_logical_model=run.requested_logical_model,
        status=run.status,
        output_preview=run.output_preview,
        latency_ms=run.latency_ms,
        error_code=run.error_code,
        tool_invocations=tool_invocations,
    )


@router.get("/v1/assistants", response_model=AssistantPresetListResponse)
def list_assistants_endpoint(
    project_id: UUID | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AssistantPresetListResponse:
    items, next_cursor = list_assistants(
        db,
        user_id=UUID(str(current_user.id)),
        project_id=project_id,
        cursor=cursor,
        limit=limit,
    )
    return AssistantPresetListResponse(
        items=[
            {
                "assistant_id": it.id,
                "project_id": it.api_key_id,
                "name": it.name,
                "system_prompt": it.system_prompt or "",
                "default_logical_model": it.default_logical_model,
                "title_logical_model": getattr(it, "title_logical_model", None),
                "created_at": it.created_at,
                "updated_at": it.updated_at,
            }
            for it in items
        ],
        next_cursor=next_cursor,
    )


@router.post("/v1/assistants", response_model=AssistantPresetResponse, status_code=status.HTTP_201_CREATED)
def create_assistant_endpoint(
    payload: AssistantPresetCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AssistantPresetResponse:
    assistant = create_assistant(
        db,
        user_id=UUID(str(current_user.id)),
        project_id=payload.project_id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        default_logical_model=payload.default_logical_model,
        title_logical_model=payload.title_logical_model,
        model_preset=payload.model_preset,
    )
    return _assistant_to_response(assistant)


@router.get("/v1/assistants/{assistant_id}", response_model=AssistantPresetResponse)
def get_assistant_endpoint(
    assistant_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AssistantPresetResponse:
    assistant = get_assistant(
        db,
        assistant_id=assistant_id,
        user_id=UUID(str(current_user.id)),
    )
    return _assistant_to_response(assistant)


@router.put("/v1/assistants/{assistant_id}", response_model=AssistantPresetResponse)
def update_assistant_endpoint(
    assistant_id: UUID,
    payload: AssistantPresetUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AssistantPresetResponse:
    assistant = update_assistant(
        db,
        assistant_id=assistant_id,
        user_id=UUID(str(current_user.id)),
        name=payload.name,
        system_prompt=payload.system_prompt,
        default_logical_model=payload.default_logical_model,
        title_logical_model=payload.title_logical_model,
        title_logical_model_set="title_logical_model" in payload.model_fields_set,
        model_preset=payload.model_preset,
        archived=payload.archived,
    )
    return _assistant_to_response(assistant)


@router.delete("/v1/assistants/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assistant_endpoint(
    assistant_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Response:
    delete_assistant(db, assistant_id=assistant_id, user_id=UUID(str(current_user.id)))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/v1/conversations", response_model=ConversationItem, status_code=status.HTTP_201_CREATED)
def create_conversation_endpoint(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict:
    conv = create_conversation(
        db,
        user_id=UUID(str(current_user.id)),
        project_id=payload.project_id,
        assistant_id=payload.assistant_id,
        title=payload.title,
    )
    return _conversation_to_item(conv)


@router.put("/v1/conversations/{conversation_id}", response_model=ConversationItem)
def update_conversation_endpoint(
    conversation_id: UUID,
    payload: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict:
    conv = update_conversation(
        db,
        conversation_id=conversation_id,
        user_id=UUID(str(current_user.id)),
        title=payload.title,
        archived=payload.archived,
        is_pinned=payload.is_pinned,
        unread_count=payload.unread_count,
        summary_text=payload.summary,
        summary_text_set="summary" in payload.model_fields_set,
    )
    return _conversation_to_item(conv)


@router.delete("/v1/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_endpoint(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Response:
    delete_conversation(db, conversation_id=conversation_id, user_id=UUID(str(current_user.id)))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/v1/conversations/{conversation_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_conversation_messages_endpoint(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Response:
    clear_conversation_messages(db, conversation_id=conversation_id, user_id=UUID(str(current_user.id)))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/v1/conversations", response_model=ConversationListResponse)
def list_conversations_endpoint(
    assistant_id: UUID = Query(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ConversationListResponse:
    items, next_cursor = list_conversations(
        db,
        user_id=UUID(str(current_user.id)),
        assistant_id=assistant_id,
        cursor=cursor,
        limit=limit,
        archived=archived,
    )
    return ConversationListResponse(
        items=[_conversation_to_item(it) for it in items],
        next_cursor=next_cursor,
    )


@router.post("/v1/conversations/{conversation_id}/messages")
async def create_message_endpoint(
    conversation_id: UUID,
    request: Request,
    payload: MessageCreateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client: Any = Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Any:
    accept_header = request.headers.get("accept", "")
    wants_event_stream = "text/event-stream" in accept_header.lower()

    # streaming=true 或 Accept:text/event-stream 均触发 SSE
    stream = bool(payload.streaming) or wants_event_stream
    # 测试环境下跳过真正的 Celery 调度，沿用“请求内执行”以避免 broker 依赖导致卡住。
    if os.getenv("PYTEST_CURRENT_TEST"):
        if stream:
            return StreamingResponse(
                chat_app_service.stream_message_and_run_baseline(
                    db,
                    redis=redis,
                    client=client,
                    current_user=current_user,
                    conversation_id=conversation_id,
                    content=payload.content,
                    override_logical_model=payload.override_logical_model,
                    model_preset=payload.model_preset,
                    bridge_agent_id=payload.bridge_agent_id,
                    bridge_agent_ids=payload.bridge_agent_ids,
                    bridge_tool_selections=payload.bridge_tool_selections,
                ),
                media_type="text/event-stream",
            )

        message_id, run_id = await chat_app_service.send_message_and_run_baseline(
            db,
            redis=redis,
            client=client,
            current_user=current_user,
            conversation_id=conversation_id,
            content=payload.content,
            override_logical_model=payload.override_logical_model,
            model_preset=payload.model_preset,
            bridge_agent_id=payload.bridge_agent_id,
            bridge_agent_ids=payload.bridge_agent_ids,
            bridge_tool_selections=payload.bridge_tool_selections,
        )
        run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
        return MessageCreateResponse(message_id=message_id, baseline_run=_run_to_summary(run))

    async def _wait_for_terminal_event(*, run_id: UUID, after_seq: int) -> None:
        last_seq = int(after_seq or 0)
        # DB replay（防止 worker 很快写完导致我们错过热通道事件）
        for ev in list_run_events(db, run_id=run_id, after_seq=last_seq, limit=1000):
            seq = int(getattr(ev, "seq", 0) or 0)
            if seq <= last_seq:
                continue
            last_seq = seq
            et = str(getattr(ev, "event_type", "") or "")
            if et in {"message.completed", "message.failed"}:
                return

        async for env in subscribe_run_events(redis, run_id=run_id, after_seq=last_seq, request=request):
            if not isinstance(env, dict):
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
            et = str(env.get("event_type") or "")
            if et in {"message.completed", "message.failed"}:
                return

    if stream:
        (
            message_id,
            run_id,
            assistant_message_id,
            created_payload,
            created_seq,
            _bridge_agent_ids,
        ) = await chat_app_service.create_message_and_queue_baseline_run(
            db,
            redis=redis,
            client=client,
            current_user=current_user,
            conversation_id=conversation_id,
            content=payload.content,
            streaming=True,
            override_logical_model=payload.override_logical_model,
            model_preset=payload.model_preset,
            bridge_agent_id=payload.bridge_agent_id,
            bridge_agent_ids=payload.bridge_agent_ids,
            bridge_tool_selections=payload.bridge_tool_selections,
        )

        async def _gen():
            last_seq = int(created_seq or 0)
            yield _encode_sse_event(event_type="message.created", data=created_payload)

            # 先回放 DB 中的缺失 message.* 事件，再订阅 Redis 热通道实时续订
            for ev in list_run_events(db, run_id=run_id, after_seq=last_seq, limit=1000):
                seq = int(getattr(ev, "seq", 0) or 0)
                if seq <= last_seq:
                    continue
                last_seq = seq
                et = str(getattr(ev, "event_type", "") or "")
                if not et.startswith("message."):
                    continue
                data = getattr(ev, "payload", None) or {}
                yield _encode_sse_event(event_type=et, data=data)
                if et in {"message.completed", "message.failed"}:
                    yield _encode_sse_event(event_type="done", data="[DONE]")
                    return

            async for env in subscribe_run_events(redis, run_id=run_id, after_seq=last_seq, request=request):
                if not isinstance(env, dict):
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

                et = str(env.get("event_type") or "")
                if not et.startswith("message."):
                    continue
                data = env.get("payload") if isinstance(env.get("payload"), dict) else {}
                yield _encode_sse_event(event_type=et, data=data)
                if et in {"message.completed", "message.failed"}:
                    break

            yield _encode_sse_event(event_type="done", data="[DONE]")

        return StreamingResponse(_gen(), media_type="text/event-stream")

    (
        message_id,
        run_id,
        _assistant_message_id,
        _created_payload,
        created_seq,
        _bridge_agent_ids,
    ) = await chat_app_service.create_message_and_queue_baseline_run(
        db,
        redis=redis,
        client=client,
        current_user=current_user,
        conversation_id=conversation_id,
        content=payload.content,
        streaming=False,
        override_logical_model=payload.override_logical_model,
        model_preset=payload.model_preset,
        bridge_agent_id=payload.bridge_agent_id,
        bridge_agent_ids=payload.bridge_agent_ids,
        bridge_tool_selections=payload.bridge_tool_selections,
    )

    await _wait_for_terminal_event(run_id=run_id, after_seq=int(created_seq or 0))
    run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
    return MessageCreateResponse(message_id=message_id, baseline_run=_run_to_summary(run))


@router.post("/v1/conversations/{conversation_id}/image-generations")
async def create_image_generation_endpoint(
    conversation_id: UUID,
    request: Request,
    payload: ConversationImageGenerationRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client: Any = Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Any:
    """
    会话内文生图（写入聊天历史）。

    - 默认推荐 SSE（streaming=true 或 Accept:text/event-stream），以获得更好的等待体验；
    - 生产环境通过 Celery 异步执行，并通过 RunEvent 推送状态；
    - 测试环境下跳过 Celery，沿用“请求内执行”。
    """
    accept_header = request.headers.get("accept", "")
    wants_event_stream = "text/event-stream" in accept_header.lower()
    stream = bool(payload.streaming) or wants_event_stream

    omit_upstream_response_format = payload.response_format is None
    image_request = payload.model_dump(exclude_none=True)
    prompt = str(image_request.pop("prompt") or "").strip()
    image_request.pop("streaming", None)

    # Chat 历史里强制使用 url（走 OSS + /media/images），避免把 b64 写入 DB。
    image_request["response_format"] = "url"
    if omit_upstream_response_format:
        extra_body = image_request.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        gateway = extra_body.get("gateway")
        if not isinstance(gateway, dict):
            gateway = {}
        gateway["omit_response_format"] = True
        extra_body["gateway"] = gateway
        image_request["extra_body"] = extra_body
    image_request["model"] = str(image_request.get("model") or "").strip()
    if not image_request["model"]:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="model required")

    # 测试环境下跳过真正的 Celery 调度，避免 broker 依赖导致卡住。
    if os.getenv("PYTEST_CURRENT_TEST"):
        (
            user_message_id,
            run_id,
            assistant_message_id,
            created_payload,
            _created_seq,
            api_key,
        ) = create_image_generation_and_queue_run(
            db,
            redis=redis,
            current_user=current_user,
            conversation_id=conversation_id,
            prompt=prompt,
            image_request=image_request,
            streaming=stream,
        )

        async def _finalize(content_with_urls: dict[str, Any]) -> None:
            # DB 持久化：只保存 object_key（url 由 list_messages 时动态续签）。
            stored = dict(content_with_urls)
            imgs = stored.get("images")
            kept: list[dict[str, Any]] = []
            if isinstance(imgs, list):
                for it in imgs:
                    if not isinstance(it, dict):
                        continue
                    obj = it.get("object_key")
                    url = it.get("url")
                    revised = it.get("revised_prompt")
                    if isinstance(obj, str) and obj.strip():
                        kept.append({"object_key": obj.strip(), "revised_prompt": revised})
                    elif isinstance(url, str) and url.strip():
                        kept.append({"url": url.strip(), "revised_prompt": revised})
            stored["images"] = kept

            user_msg = db.get(Message, user_message_id)
            if user_msg is None:
                return
            finalize_assistant_image_generation_after_user_sequence(
                db,
                conversation_id=conversation_id,
                user_sequence=int(getattr(user_msg, "sequence", 0) or 0),
                content=stored,
                preview_text=f"[图片] {prompt[:60]}",
            )

        async def _gen():
            if stream:
                yield _encode_sse_event(event_type="message.created", data=created_payload)
                yield _encode_sse_event(
                    event_type="message.delta",
                    data={
                        "type": "message.delta",
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id) if assistant_message_id else None,
                        "delta": "正在生成图片…",
                        "kind": "image_generation",
                    },
                )

            content_with_urls = await execute_image_generation_inline(
                db=db,
                redis=redis,
                client=client,
                api_key=api_key,
                prompt=prompt,
                image_request=image_request,
            )
            await _finalize(content_with_urls)

            run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
            run.status = "succeeded"
            run.output_preview = f"[图片] {prompt[:60]}".strip()
            run.response_payload = content_with_urls
            db.add(run)
            db.commit()

            if stream:
                yield _encode_sse_event(
                    event_type="message.completed",
                    data={
                        "type": "message.completed",
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id) if assistant_message_id else None,
                        "baseline_run": _run_to_summary(run),
                        "kind": "image_generation",
                        "image_generation": content_with_urls,
                    },
                )
                yield _encode_sse_event(event_type="done", data="[DONE]")
            else:
                return

        if stream:
            return StreamingResponse(_gen(), media_type="text/event-stream")

        content_with_urls = await execute_image_generation_inline(
            db=db,
            redis=redis,
            client=client,
            api_key=api_key,
            prompt=prompt,
            image_request=image_request,
        )
        await _finalize(content_with_urls)
        run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
        run.status = "succeeded"
        run.output_preview = f"[图片] {prompt[:60]}".strip()
        run.response_payload = content_with_urls
        db.add(run)
        db.commit()
        return MessageCreateResponse(message_id=user_message_id, baseline_run=_run_to_summary(run))

    (
        message_id,
        run_id,
        assistant_message_id,
        created_payload,
        created_seq,
        _api_key,
    ) = create_image_generation_and_queue_run(
        db,
        redis=redis,
        current_user=current_user,
        conversation_id=conversation_id,
        prompt=prompt,
        image_request=image_request,
        streaming=stream,
    )

    try:
        from app.celery_app import celery_app

        celery_app.send_task(
            "tasks.execute_image_generation_run",
            args=[str(run_id), str(assistant_message_id) if assistant_message_id is not None else None, bool(stream)],
        )
    except Exception:
        # 入队失败：让后续等待流程/前端拿到明确失败（由 run 终态事件驱动），这里不吞掉错误。
        raise

    async def _wait_for_terminal_event(*, run_id: UUID, after_seq: int) -> None:
        last_seq = int(after_seq or 0)
        for ev in list_run_events(db, run_id=run_id, after_seq=last_seq, limit=1000):
            seq = int(getattr(ev, "seq", 0) or 0)
            if seq <= last_seq:
                continue
            last_seq = seq
            et = str(getattr(ev, "event_type", "") or "")
            if et in {"message.completed", "message.failed"}:
                return

        async for env in subscribe_run_events(redis, run_id=run_id, after_seq=last_seq, request=request):
            if not isinstance(env, dict):
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
            et = str(env.get("event_type") or "")
            if et in {"message.completed", "message.failed"}:
                return

    if stream:
        async def _gen():
            last_seq = int(created_seq or 0)
            yield _encode_sse_event(event_type="message.created", data=created_payload)

            for ev in list_run_events(db, run_id=run_id, after_seq=last_seq, limit=1000):
                seq = int(getattr(ev, "seq", 0) or 0)
                if seq <= last_seq:
                    continue
                last_seq = seq
                et = str(getattr(ev, "event_type", "") or "")
                if not et.startswith("message."):
                    continue
                data = getattr(ev, "payload", None) or {}
                if et == "message.completed" and isinstance(data, dict):
                    img = data.get("image_generation")
                    if isinstance(img, dict):
                        data["image_generation"] = _hydrate_image_generation_content(img)
                yield _encode_sse_event(event_type=et, data=data)
                if et in {"message.completed", "message.failed"}:
                    yield _encode_sse_event(event_type="done", data="[DONE]")
                    return

            async for env in subscribe_run_events(redis, run_id=run_id, after_seq=last_seq, request=request):
                if not isinstance(env, dict):
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

                et = str(env.get("event_type") or "")
                if not et.startswith("message."):
                    continue
                data = env.get("payload") if isinstance(env.get("payload"), dict) else {}
                if et == "message.completed" and isinstance(data, dict):
                    img = data.get("image_generation")
                    if isinstance(img, dict):
                        data["image_generation"] = _hydrate_image_generation_content(img)
                yield _encode_sse_event(event_type=et, data=data)
                if et in {"message.completed", "message.failed"}:
                    break

            yield _encode_sse_event(event_type="done", data="[DONE]")

        return StreamingResponse(_gen(), media_type="text/event-stream")

    await _wait_for_terminal_event(run_id=run_id, after_seq=int(created_seq or 0))
    run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
    return MessageCreateResponse(message_id=message_id, baseline_run=_run_to_summary(run))


@router.get("/v1/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages_endpoint(
    conversation_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> MessageListResponse:
    messages, runs_by_message, next_cursor = list_messages_with_run_summaries(
        db,
        conversation_id=conversation_id,
        user_id=UUID(str(current_user.id)),
        cursor=cursor,
        limit=limit,
    )

    items = []
    for msg in messages:
        runs = runs_by_message.get(UUID(str(msg.id)), []) if msg.role == "user" else []
        content = msg.content
        if isinstance(content, dict) and str(content.get("type") or "") == "image_generation":
            content = _hydrate_image_generation_content(content)
        items.append(
            {
                "message_id": msg.id,
                "role": msg.role,
                "content": content,
                "created_at": msg.created_at,
                "runs": [_run_to_summary(r) for r in runs],
            }
        )

    return MessageListResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/runs/{run_id}", response_model=RunDetailResponse)
def get_run_endpoint(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> RunDetailResponse:
    run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
    return RunDetailResponse(
        run_id=run.id,
        message_id=run.message_id,
        requested_logical_model=run.requested_logical_model,
        selected_provider_id=run.selected_provider_id,
        selected_provider_model=run.selected_provider_model,
        status=run.status,
        output_preview=run.output_preview,
        output_text=run.output_text,
        request_payload=run.request_payload,
        response_payload=run.response_payload,
        latency_ms=run.latency_ms,
        error_code=run.error_code,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.post("/v1/runs/{run_id}/cancel", response_model=RunDetailResponse)
async def cancel_run_endpoint(
    run_id: UUID,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> RunDetailResponse:
    """
    取消一个 run（best-effort）：
    - 写入 Redis cancel 标记，供 worker 及时终止；
    - 将 run 状态置为 canceled，并追加 run.canceled / message.failed 事件（便于 SSE 订阅方收敛终态）。
    """
    run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))

    try:
        await mark_run_canceled(redis, run_id=run_id)
    except Exception:
        # cancel flag 失败不阻断（仍尽量写 DB 终态）
        pass

    if str(run.status or "") not in {"succeeded", "failed", "canceled"}:
        run.status = "canceled"
        run.error_code = "CANCELED"
        run.error_message = "canceled"
        run.finished_at = datetime.now(UTC)
        db.add(run)
        db.commit()
        db.refresh(run)

        def _append_and_publish(event_type: str, payload: dict[str, Any]) -> None:
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

        _append_and_publish("run.canceled", {"type": "run.canceled", "run_id": str(run_id)})

        # 尽量补齐 message.failed payload 的上下文字段（用于兼容 message.* SSE 消费者）
        conv_id = None
        user_message_id = None
        assistant_message_id = None
        msg = db.execute(select(Message).where(Message.id == run.message_id)).scalars().first()
        if msg is not None:
            conv_id = str(msg.conversation_id)
            user_message_id = str(msg.id)
            try:
                assistant_seq = int(msg.sequence or 0) + 1
                assistant_msg = (
                    db.execute(
                        select(Message).where(
                            Message.conversation_id == msg.conversation_id,
                            Message.sequence == assistant_seq,
                            Message.role == "assistant",
                        )
                    )
                    .scalars()
                    .first()
                )
                if assistant_msg is not None:
                    assistant_message_id = str(assistant_msg.id)
            except Exception:
                assistant_message_id = None

        _append_and_publish(
            "message.failed",
            {
                "type": "message.failed",
                "conversation_id": conv_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "baseline_run": _run_to_summary(run).model_dump(mode="json"),
                "output_text": None,
            },
        )

    return RunDetailResponse(
        run_id=run.id,
        message_id=run.message_id,
        requested_logical_model=run.requested_logical_model,
        selected_provider_id=run.selected_provider_id,
        selected_provider_model=run.selected_provider_model,
        status=run.status,
        output_preview=run.output_preview,
        output_text=run.output_text,
        request_payload=run.request_payload,
        response_payload=run.response_payload,
        latency_ms=run.latency_ms,
        error_code=run.error_code,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/v1/runs/{run_id}/events")
async def stream_run_events_endpoint(
    run_id: UUID,
    request: Request,
    after_seq: int | None = Query(default=None, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> StreamingResponse:
    """
    RunEvent 事件流订阅（SSE replay）：
    - 先从 DB 真相回放缺失事件（after_seq 之后）
    - 再订阅 Redis 热通道实时接收新事件
    """
    _ = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))

    last_seq = int(after_seq or 0)

    async def _gen():
        nonlocal last_seq
        # 先订阅 Redis，再进行 DB replay：避免 replay 与 subscribe 之间的时间窗导致事件丢失。
        channel = run_event_channel(run_id=run_id)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        last_activity = time.monotonic()

        try:
            # DB 真相回放（after_seq 之后）
            for ev in list_run_events(db, run_id=run_id, after_seq=last_seq, limit=limit):
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

            # Redis 热通道实时续订
            while True:
                try:
                    if await request.is_disconnected():
                        break
                except Exception:  # pragma: no cover
                    break

                msg: dict[str, Any] | None
                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except Exception:
                    msg = None

                if isinstance(msg, dict) and msg.get("type") == "message":
                    raw = msg.get("data")
                    if isinstance(raw, (bytes, bytearray)):
                        raw_str = raw.decode("utf-8", errors="ignore")
                    elif isinstance(raw, str):
                        raw_str = raw
                    else:
                        raw_str = ""

                    env: dict[str, Any] | None = None
                    if raw_str:
                        try:
                            parsed = json.loads(raw_str)
                            if isinstance(parsed, dict):
                                env = parsed
                        except Exception:
                            env = None

                    if not isinstance(env, dict):
                        continue

                    if str(env.get("type") or "") == "heartbeat":
                        yield _encode_sse_event(event_type="heartbeat", data=env)
                        continue

                    try:
                        seq = int(env.get("seq") or 0)
                    except Exception:
                        seq = 0
                    if seq <= last_seq:
                        continue

                    last_seq = seq
                    last_activity = time.monotonic()
                    event_type = str(env.get("event_type") or "run.event")
                    yield _encode_sse_event(event_type=event_type, data=env)
                    continue

                if time.monotonic() - last_activity >= 15.0:
                    last_activity = time.monotonic()
                    yield _encode_sse_event(
                        event_type="heartbeat",
                        data={"type": "heartbeat", "ts": int(time.time()), "run_id": str(run_id), "after_seq": last_seq},
                    )
        except Exception:
            return
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(channel)
            with suppress(Exception):
                await pubsub.close()

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.post("/v1/messages/{assistant_message_id}/regenerate", response_model=MessageRegenerateResponse)
async def regenerate_message_endpoint(
    assistant_message_id: UUID,
    payload: MessageRegenerateRequest | None = None,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client: Any = Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> MessageRegenerateResponse:
    assistant_message_id, run_id = await chat_app_service.regenerate_assistant_message(
        db,
        redis=redis,
        client=client,
        current_user=current_user,
        assistant_message_id=assistant_message_id,
        override_logical_model=(payload.override_logical_model if payload is not None else None),
        model_preset=(payload.model_preset if payload is not None else None),
        bridge_agent_id=(payload.bridge_agent_id if payload is not None else None),
        bridge_agent_ids=(payload.bridge_agent_ids if payload is not None else None),
        bridge_tool_selections=(payload.bridge_tool_selections if payload is not None else None),
    )
    run = get_run_detail(db, run_id=run_id, user_id=UUID(str(current_user.id)))
    return MessageRegenerateResponse(
        assistant_message_id=assistant_message_id,
        baseline_run=_run_to_summary(run),
    )


@router.delete("/v1/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_endpoint(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    delete_message(db, message_id=message_id, user_id=UUID(str(current_user.id)))


__all__ = ["router"]
