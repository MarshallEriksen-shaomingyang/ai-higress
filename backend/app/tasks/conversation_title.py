from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.db.session import SessionLocal
from app.http_client import CurlCffiClient
from app.jwt_auth import AuthenticatedUser
from app.logging_config import logger
from app.models import APIKey, AssistantPreset, Conversation, Message, User
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.services.chat_app_service import _maybe_auto_title_conversation
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
)
from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - 兼容无 redis 依赖的测试环境
    Redis = object  # type: ignore[misc,assignment]


def _get_title_session_factory():
    return SessionLocal


def _get_title_redis() -> Redis:
    return get_redis_client()


@asynccontextmanager
async def _title_http_client():
    async with CurlCffiClient(
        timeout=settings.upstream_timeout,
        impersonate="chrome120",
        trust_env=True,
    ) as client:
        yield client


async def generate_conversation_title(
    conversation_id: str,
    message_id: str,
    user_id: str,
    assistant_id: str,
    requested_model_for_title_fallback: str | None,
) -> str:
    """
    异步生成会话标题（在 Celery 任务或测试中复用）。
    """
    SessionFactory = _get_title_session_factory()
    with SessionFactory() as db:
        conv = (
            db.execute(
                select(Conversation).where(
                    Conversation.id == UUID(str(conversation_id)),
                    Conversation.user_id == UUID(str(user_id)),
                )
            )
            .scalars()
            .first()
        )
        if conv is None:
            return "skipped:no_conversation"
        if (conv.title or "").strip():
            return "skipped:title_exists"

        message = db.execute(select(Message).where(Message.id == UUID(str(message_id)))).scalars().first()
        if message is None:
            return "skipped:no_message"
        if int(message.sequence or 0) != 1:
            return "skipped:not_first_message"

        assistant = db.execute(select(AssistantPreset).where(AssistantPreset.id == UUID(str(assistant_id)))).scalars().first()
        if assistant is None:
            return "skipped:no_assistant"

        user = db.execute(select(User).where(User.id == UUID(str(user_id)))).scalars().first()
        if user is None:
            return "skipped:no_user"
        if not bool(user.is_active):
            return "skipped:user_inactive"

        api_key = db.execute(select(APIKey).where(APIKey.id == UUID(str(conv.api_key_id)))).scalars().first()
        if api_key is None:
            return "skipped:no_api_key"

        cfg = get_or_default_project_eval_config(db, project_id=UUID(str(api_key.id)))
        effective_provider_ids = get_effective_provider_ids_for_user(
            db,
            user_id=UUID(str(user.id)),
            api_key=api_key,
            provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
        )

        auth_user = AuthenticatedUser(
            id=str(user.id),
            username=user.username,
            email=user.email,
            is_superuser=bool(user.is_superuser),
            is_active=bool(user.is_active),
            display_name=getattr(user, "display_name", None),
            avatar=None,
        )

        redis = _get_title_redis()
        try:
            async with _title_http_client() as client:
                def _safe_user_text(value: Any) -> str:
                    if isinstance(value, str):
                        return value
                    if isinstance(value, dict):
                        text = value.get("text")
                        if isinstance(text, str):
                            return text
                    return ""

                await _maybe_auto_title_conversation(
                    db,
                    redis=redis,
                    client=client,
                    current_user=auth_user,
                    conv=conv,
                    assistant=assistant,
                    effective_provider_ids=effective_provider_ids,
                    user_text=_safe_user_text(message.content),
                    user_sequence=int(message.sequence or 0),
                    requested_model_for_title_fallback=requested_model_for_title_fallback or "",
                )
        finally:
            await close_redis_client_for_current_loop()
        return "done"


@shared_task(name="tasks.generate_conversation_title")
def generate_conversation_title_task(
    conversation_id: str,
    message_id: str,
    user_id: str,
    assistant_id: str,
    requested_model_for_title_fallback: str | None = None,
) -> str:
    try:
        return asyncio.run(
            generate_conversation_title(
                conversation_id=conversation_id,
                message_id=message_id,
                user_id=user_id,
                assistant_id=assistant_id,
                requested_model_for_title_fallback=requested_model_for_title_fallback,
            )
        )
    except Exception as exc:  # pragma: no cover - Celery worker内部兜底
        logger.exception("conversation_title task failed: %s", exc)
        return "failed"


__all__ = [
    "generate_conversation_title",
    "generate_conversation_title_task",
]
