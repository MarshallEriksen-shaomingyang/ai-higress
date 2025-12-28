from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.models import Conversation, Message
from app.settings import settings


def _safe_text_from_message_content(content: Any) -> str:
    if not isinstance(content, dict):
        return ""
    if str(content.get("type") or "") == "text":
        text = content.get("text")
        if isinstance(text, str):
            return text
    text = content.get("text")
    if isinstance(text, str):
        return text
    return ""


def _extract_first_choice_text(payload: dict[str, Any] | None) -> str | None:
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
    content = first.get("text")
    if isinstance(content, str) and content.strip():
        return content
    return None


def _parse_json_response_body(resp: JSONResponse) -> dict[str, Any] | None:
    try:
        raw = resp.body.decode("utf-8", errors="ignore")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _build_delta_transcript(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = str(getattr(msg, "role", "") or "").strip() or "user"
        text = _safe_text_from_message_content(getattr(msg, "content", None))
        text = (text or "").strip()
        if not text:
            continue
        lines.append(f"{role}: {text}")
    return "\n".join(lines).strip()


async def maybe_update_conversation_summary(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    conversation_id: UUID,
    assistant_id: UUID | None,
    requested_logical_model: str,
    new_until_sequence: int,
    force: bool = False,
) -> bool:
    """
    增量更新会话摘要（best-effort）：

    - 当会话消息数量达到 `CHAT_CONTEXT_MAX_MESSAGES`（按条数）时开始生成摘要；
    - 之后每次有新 assistant 终态消息，会把“上次摘要覆盖点 -> 本次序号”的增量消息合并进摘要；
    - 上游调用使用与本次对话相同的 logical_model（requested_logical_model）。
    """
    threshold = int(getattr(settings, "chat_context_max_messages", 0) or 0)
    if threshold <= 0:
        return False

    conv = db.get(Conversation, conversation_id)
    if conv is None:
        return False

    existing_summary = (getattr(conv, "summary_text", None) or "").strip()
    current_until = int(getattr(conv, "summary_until_sequence", 0) or 0)
    target_until = int(new_until_sequence or 0)
    if target_until <= 0 or target_until <= current_until:
        return False

    # 未达到阈值时不自动生成首份摘要；force=True 可用于未来手动触发。
    if not force and not existing_summary and target_until < threshold:
        return False

    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sequence > current_until,
            Message.sequence <= target_until,
        )
        .order_by(Message.sequence.asc())
    )
    delta_messages = list(db.execute(stmt).scalars().all())
    delta_text = _build_delta_transcript(delta_messages)
    if not delta_text:
        return False

    system_prompt = (
        "You are a conversation summarizer.\n"
        "You maintain a running summary for a chat conversation.\n"
        "The summary is shown to the user and will be used as the ONLY long-term context for future replies.\n"
        "Requirements:\n"
        "- Keep key facts, decisions, constraints, user preferences, open questions, and TODOs.\n"
        "- Remove fluff and repetition.\n"
        "- Do NOT include secrets (API keys, passwords, tokens) even if they appear in messages.\n"
        "- Write in the dominant language of the conversation.\n"
        "- Output plain text only (no markdown), max ~800 Chinese chars or ~500 words.\n"
    )

    if existing_summary:
        user_prompt = (
            "Current summary:\n"
            f"{existing_summary}\n\n"
            "New messages to merge:\n"
            f"{delta_text}\n"
        )
    else:
        user_prompt = f"Conversation transcript:\n{delta_text}\n"

    model = str(requested_logical_model or "").strip()
    if not model:
        return False

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
    }

    handler = RequestHandler(api_key=api_key, db=db, redis=redis, client=client)
    resp = await handler.handle(
        payload=payload,
        requested_model=model,
        lookup_model_id=model,
        api_style="openai",
        effective_provider_ids=effective_provider_ids,
        session_id=str(conversation_id),
        assistant_id=assistant_id,
        idempotency_key=f"summary:{conversation_id}:{target_until}",
        billing_reason="conversation_summary",
    )

    response_payload = _parse_json_response_body(resp)
    summary = (_extract_first_choice_text(response_payload) or "").strip()
    if not summary:
        return False

    conv.summary_text = summary
    conv.summary_until_sequence = target_until
    conv.summary_updated_at = datetime.now(UTC)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    logger.info(
        "conversation_summary: updated conversation_id=%s until=%s summary_len=%d",
        str(conversation_id),
        target_until,
        len(summary),
    )
    return True


__all__ = ["maybe_update_conversation_summary"]

