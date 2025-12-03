"""
Session management helpers for conversation stickiness.

These helpers wrap the lower-level Redis storage helpers and provide a
clean interface for routing/scheduler logic to bind and retrieve
conversation sessions.
"""

from __future__ import annotations

import time

from app.schemas import Session
from app.redis_client import redis_delete
from app.storage.redis_service import get_session as storage_get_session
from app.storage.redis_service import set_session as storage_set_session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]


async def get_session(redis: Redis, conversation_id: str) -> Session | None:
    """
    Load a session from Redis if present.
    """
    return await storage_get_session(redis, conversation_id)


async def bind_session(
    redis: Redis,
    *,
    conversation_id: str,
    logical_model: str,
    provider_id: str,
    model_id: str,
    ts: float | None = None,
) -> Session:
    """
    Create or replace a session binding for a conversation.
    """
    now = ts or time.time()
    existing = await storage_get_session(redis, conversation_id)
    if existing:
        session = existing.model_copy()
        session.logical_model = logical_model
        session.provider_id = provider_id
        session.model_id = model_id
        session.last_accessed = now
    else:
        session = Session(
            conversation_id=conversation_id,
            logical_model=logical_model,
            provider_id=provider_id,
            model_id=model_id,
            created_at=now,
            last_accessed=now,
            message_count=0,
        )
    await storage_set_session(redis, session)
    return session


async def touch_session(
    redis: Redis, conversation_id: str, *, increment_messages: int = 1
) -> Session | None:
    """
    Update last_accessed and message_count for an existing session.
    Returns the updated session, or None if no session exists.
    """
    existing = await storage_get_session(redis, conversation_id)
    if not existing:
        return None
    session = existing.model_copy()
    session.last_accessed = time.time()
    session.message_count += max(0, increment_messages)
    await storage_set_session(redis, session)
    return session


async def delete_session(redis: Redis, conversation_id: str) -> bool:
    """
    Delete a session key; returns True if the key existed.
    """
    session = await storage_get_session(redis, conversation_id)
    if not session:
        return False
    from app.storage.redis_service import SESSION_KEY_TEMPLATE

    key = SESSION_KEY_TEMPLATE.format(conversation_id=conversation_id)
    await redis_delete(redis, key)
    return True


__all__ = ["bind_session", "delete_session", "get_session", "touch_session"]

