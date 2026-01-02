from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.models import AssistantPreset, Conversation, Message, Run
from app.services.credit_service import compute_chat_completion_cost_credits
from app.settings import settings
from app.upstream import detect_request_format


def _safe_text_from_message_content(content: dict) -> str:
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    if isinstance(text, str):
        return text
    return ""

def _infer_audio_format_from_object_key(object_key: str) -> str:
    key = str(object_key or "").strip().lower()
    if key.endswith(".mp3"):
        return "mp3"
    return "wav"


def _build_openai_message_content_from_db_content(content: Any) -> Any:
    """
    将 DB 中的 message.content（结构化 dict）转为 OpenAI chat.completions 的 message.content：
    - 纯文本：返回 string
    - 带 input_audio：返回 list[parts]（包含 text + input_audio，其中 input_audio 先保留 object_key）
    """
    if not isinstance(content, dict):
        return None

    text = _safe_text_from_message_content(content)

    input_audio = content.get("input_audio")
    if isinstance(input_audio, dict):
        object_key = input_audio.get("object_key")
        if isinstance(object_key, str) and object_key.strip():
            fmt = input_audio.get("format")
            fmt = str(fmt or "").strip().lower()
            if fmt not in {"wav", "mp3"}:
                fmt = _infer_audio_format_from_object_key(object_key)
            parts: list[dict[str, Any]] = []
            if isinstance(text, str) and text.strip():
                parts.append({"type": "text", "text": text})
            parts.append({"type": "input_audio", "input_audio": {"object_key": object_key.strip(), "format": fmt}})
            return parts

    if isinstance(text, str) and text.strip():
        return text
    return None


def _extract_assistant_text_from_openai_response(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    # Fallback: some providers return `text` field
    content = first.get("text")
    if isinstance(content, str) and content.strip():
        return content
    return None


def _safe_inline_json(value: Any, *, max_len: int = 160) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        text = str(value)
    text = (text or "").strip().replace("\r", " ").replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


def _build_deterministic_attribute_system_block(db: Session, *, conversation: Conversation) -> str:
    """
    Build a deterministic instruction block from structured attributes (PostgreSQL).

    This is different from Qdrant semantic memory: these values are treated as
    hard preferences/constraints and should be stable key-value facts.
    """
    try:
        from app.repositories.kb_attribute_repository import list_attributes, make_subject_id

        user_sid = make_subject_id(scope="user", user_id=UUID(str(conversation.user_id)))
        proj_sid = make_subject_id(scope="project", project_id=UUID(str(conversation.api_key_id)))

        user_attrs = list_attributes(db, subject_id=user_sid, limit=50)
        proj_attrs = list_attributes(db, subject_id=proj_sid, limit=50)
    except Exception:
        return ""

    if not user_attrs and not proj_attrs:
        return ""

    lines: list[str] = []
    lines.append("以下为结构化偏好/约束（确定性配置，优先级高于普通对话内容）：")
    if user_attrs:
        lines.append("用户偏好（user preferences）：")
        for it in user_attrs[:20]:
            lines.append(f"- {it.key} = {_safe_inline_json(it.value)}")
    if proj_attrs:
        lines.append("项目约束（project constraints）：")
        for it in proj_attrs[:20]:
            lines.append(f"- {it.key} = {_safe_inline_json(it.value)}")
    lines.append("规则：如果用户当前请求与上述偏好/约束冲突，请提示冲突并请求确认。")
    return "\n".join(lines).strip()


def _build_openai_messages(
    db: Session,
    *,
    conversation_id: UUID,
    assistant: AssistantPreset,
    new_user_message: Message,
) -> list[dict[str, Any]]:
    """
    构造 OpenAI chat.completions 的 messages 数组：
    - system: assistant.system_prompt（若非空）
    - 取历史 messages（按 sequence 升序）
    - 最后追加本次 user message（若还未入库也可直接拼接）
    """
    conv = db.get(Conversation, conversation_id)
    summary_text = (getattr(conv, "summary_text", None) or "").strip() if conv is not None else ""
    summary_until = int(getattr(conv, "summary_until_sequence", 0) or 0) if conv is not None else 0

    max_history_messages = int(getattr(settings, "chat_context_max_messages", 0) or 0)
    if max_history_messages > 0:
        # 只取最近 N 条历史消息（额外 +1 是为了包含并跳过本次 new_user_message 后仍能保留 N 条历史）
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if summary_text and summary_until > 0:
            stmt = stmt.where(Message.sequence > summary_until)
        stmt = stmt.order_by(Message.sequence.desc()).limit(max_history_messages + 1)
        history_desc = list(db.execute(stmt).scalars().all())
        history = list(reversed(history_desc))
    else:
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if summary_text and summary_until > 0:
            stmt = stmt.where(Message.sequence > summary_until)
        stmt = stmt.order_by(Message.sequence.asc())
        history = list(db.execute(stmt).scalars().all())

    messages: list[dict[str, Any]] = []
    system_prompt = (assistant.system_prompt or "").strip()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    deterministic_block = _build_deterministic_attribute_system_block(db, conversation=conv) if conv is not None else ""
    if deterministic_block:
        messages.append({"role": "system", "content": deterministic_block})
    if summary_text and summary_until > 0:
        messages.append({"role": "system", "content": f"Conversation summary:\n{summary_text}"})

    for msg in history:
        if msg.id == new_user_message.id:
            continue
        role = str(msg.role or "").strip() or "user"
        if role not in {"user", "assistant", "system"}:
            role = "user"
        content_value = _build_openai_message_content_from_db_content(msg.content)
        if content_value is None:
            continue
        messages.append({"role": role, "content": content_value})

    # append new message
    new_content_value = _build_openai_message_content_from_db_content(new_user_message.content)
    if new_content_value is not None:
        messages.append({"role": "user", "content": new_content_value})
    return messages


def _merge_model_preset(base: dict | None, override: dict | None) -> dict:
    merged: dict = {}
    if isinstance(base, dict):
        merged.update(base)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def build_openai_request_payload(
    db: Session,
    *,
    conversation: Conversation,
    assistant: AssistantPreset,
    user_message: Message,
    requested_logical_model: str,
    model_preset_override: dict | None = None,
) -> dict[str, Any]:
    messages = _build_openai_messages(
        db,
        conversation_id=UUID(str(conversation.id)),
        assistant=assistant,
        new_user_message=user_message,
    )
    preset = _merge_model_preset(assistant.model_preset, model_preset_override)
    return {"model": requested_logical_model, "messages": messages, **preset}


def create_run_record(
    db: Session,
    *,
    user_id: UUID,
    api_key_id: UUID,
    message_id: UUID,
    requested_logical_model: str,
    request_payload: dict[str, Any],
    status: str = "running",
) -> Run:
    status = str(status or "").strip() or "running"
    run = Run(
        message_id=message_id,
        user_id=user_id,
        api_key_id=api_key_id,
        requested_logical_model=requested_logical_model,
        selected_provider_id=None,
        selected_provider_model=None,
        status=status,
        started_at=datetime.now(UTC) if status == "running" else None,
        finished_at=None,
        latency_ms=None,
        cost_credits=None,
        error_code=None,
        error_message=None,
        request_payload=request_payload,
        response_payload=None,
        output_text=None,
        output_preview=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


async def execute_run_non_stream(
    db: Session,
    *,
    redis: Redis,
    client: httpx.AsyncClient,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    conversation: Conversation,
    assistant: AssistantPreset,
    user_message: Message,
    run: Run,
    requested_logical_model: str,
    model_preset_override: dict | None = None,
    payload_override: dict[str, Any] | None = None,
) -> Run:
    """
    执行一次 non-stream run，并把结果写回 Run 记录。
    """
    start = time.time()

    try:
        if payload_override is not None:
            payload = dict(payload_override)
        else:
            payload = build_openai_request_payload(
                db,
                conversation=conversation,
                assistant=assistant,
                user_message=user_message,
                requested_logical_model=requested_logical_model,
                model_preset_override=model_preset_override,
            )
        api_style = detect_request_format(payload)

        selected: dict[str, str | None] = {"provider_id": None, "model_id": None}

        def _sink(provider_id: str, model_id: str) -> None:
            selected["provider_id"] = provider_id
            selected["model_id"] = model_id

        handler = RequestHandler(api_key=api_key, db=db, redis=redis, client=client)
        response = await handler.handle(
            payload=payload,
            requested_model=requested_logical_model,
            lookup_model_id=requested_logical_model,
            api_style=api_style,
            effective_provider_ids=effective_provider_ids,
            session_id=str(conversation.id),
            assistant_id=UUID(str(assistant.id)),
            provider_id_sink=_sink,
        )

        response_payload: dict[str, Any] | None = None
        try:
            if isinstance(response.body, (bytes, bytearray)):
                parsed = httpx.Response(200, content=response.body).json()
            else:
                parsed = None
            if isinstance(parsed, dict):
                response_payload = parsed
        except Exception:
            response_payload = None

        output_text = _extract_assistant_text_from_openai_response(response_payload)
        output_preview = (output_text or "").strip()
        if output_preview:
            output_preview = output_preview[:380].rstrip()
        else:
            output_preview = None

        is_failed = response.status_code >= 400
        run.status = "failed" if is_failed else "succeeded"
        run.selected_provider_id = selected.get("provider_id")
        run.selected_provider_model = selected.get("model_id")
        run.cost_credits = compute_chat_completion_cost_credits(
            db,
            logical_model_name=requested_logical_model,
            provider_id=run.selected_provider_id,
            provider_model_id=run.selected_provider_model,
            response_payload=response_payload,
            request_payload=payload,
        )
        if is_failed:
            run.error_code = "UPSTREAM_ERROR"
            if isinstance(response_payload, dict):
                err = response_payload.get("error")
                if isinstance(err, dict):
                    err_type = err.get("type")
                    if isinstance(err_type, str) and err_type.strip():
                        run.error_code = err_type.strip()
                    run.error_message = str(err.get("message") or err.get("type") or "upstream_error")
                elif err is not None:
                    run.error_message = str(err)
        run.response_payload = response_payload
        run.output_text = output_text
        run.output_preview = output_preview
        run.latency_ms = int(max(0, (time.time() - start) * 1000))
        run.finished_at = datetime.now(UTC)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    except HTTPException as exc:
        run.status = "failed"
        run.error_code = "UPSTREAM_ERROR"
        run.error_message = str(exc.detail)
        run.latency_ms = int(max(0, (time.time() - start) * 1000))
        run.finished_at = datetime.now(UTC)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:  # pragma: no cover
        logger.exception("chat_run_service: run failed (run_id=%s): %s", run.id, exc)
        run.status = "failed"
        run.error_code = "INTERNAL_ERROR"
        run.error_message = str(exc)
        run.latency_ms = int(max(0, (time.time() - start) * 1000))
        run.finished_at = datetime.now(UTC)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run


__all__ = ["build_openai_request_payload", "create_run_record", "execute_run_non_stream"]
