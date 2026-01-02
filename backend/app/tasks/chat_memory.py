from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from celery import shared_task
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.models import APIKey, Conversation, Message, User
from app.qdrant_client import QdrantNotConfigured, close_qdrant_client_for_current_loop, get_qdrant_client, qdrant_is_configured
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.settings import settings
from app.services.embedding_service import embed_text
from app.services.system_config_service import get_kb_global_embedding_logical_model
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
)
from app.services.qdrant_collection_service import ensure_collection_ready
from app.services.qdrant_bootstrap_service import ensure_system_collection_ready
from app.services.chat_memory_router import route_chat_memory
from app.repositories.kb_attribute_repository import make_subject_id, upsert_attribute
from app.storage.qdrant_kb_store import upsert_point
from app.utils.response_utils import safe_text_from_message_content


_IDLE_SECONDS = 300
_BATCH_LIMIT = 50

memory_debug_logger = logging.getLogger("apiproxy.memory_debug")


def _enqueue_next_batch_best_effort(*, conversation_id: UUID, user_id: UUID, until_sequence: int) -> None:
    """
    Tail-recursion style: process one batch per task, then self-dispatch if backlog remains.

    Must be best-effort: enqueue failures must not break the current batch completion.
    """
    try:
        from app.celery_app import celery_app

        celery_app.send_task(
            "tasks.extract_chat_memory",
            args=[str(conversation_id), str(user_id), int(until_sequence)],
            countdown=0,
        )
    except Exception:  # pragma: no cover
        pass


def _preview_text(value: str | None, *, limit: int = 200) -> str:
    text = (value or "").strip().replace("\r", " ").replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _build_transcript(*, summary_text: str | None, messages: list[Message]) -> str:
    lines: list[str] = []
    summary = (summary_text or "").strip()
    if summary:
        lines.append("Conversation summary:")
        lines.append(summary)
        lines.append("")
        lines.append("New messages:")
    for msg in messages:
        role = str(getattr(msg, "role", "") or "").strip() or "user"
        text = safe_text_from_message_content(getattr(msg, "content", None))
        text = (text or "").strip()
        if not text:
            continue
        lines.append(f"{role}: {text}")
    return "\n".join(lines).strip()


def _to_authenticated_api_key(*, api_key: APIKey, user: User):
    from app.auth import AuthenticatedAPIKey

    return AuthenticatedAPIKey(
        id=UUID(str(api_key.id)),
        user_id=UUID(str(api_key.user_id)),
        user_username=str(user.username or ""),
        is_superuser=bool(user.is_superuser),
        name=str(api_key.name or ""),
        is_active=bool(api_key.is_active),
        disabled_reason=getattr(api_key, "disabled_reason", None),
        has_provider_restrictions=bool(api_key.has_provider_restrictions),
        allowed_provider_ids=list(api_key.allowed_provider_ids),
    )


async def extract_and_store_chat_memory(
    *,
    conversation_id: UUID,
    user_id: UUID,
    until_sequence: int,
) -> str:
    if not qdrant_is_configured():
        return "skipped:qdrant_disabled"

    if until_sequence <= 0:
        return "skipped:bad_until_sequence"

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not bool(user.is_active):
            return "skipped:user_missing_or_inactive"

        conv = db.get(Conversation, conversation_id)
        if conv is None or str(getattr(conv, "user_id", "")) != str(user_id):
            return "skipped:conversation_missing"

        api_key = db.get(APIKey, UUID(str(getattr(conv, "api_key_id"))))
        if api_key is None or str(getattr(api_key, "user_id", "")) != str(user_id):
            return "skipped:project_missing"

        last_activity = getattr(conv, "last_activity_at", None)
        if last_activity is not None:
            try:
                idle_s = (datetime.now(UTC) - last_activity).total_seconds()
                if idle_s < _IDLE_SECONDS:
                    return "skipped:not_idle"
            except Exception:
                pass

        max_seq = (
            db.execute(
                select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
            )
            .scalars()
            .first()
        )
        max_seq_int = int(max_seq or 0)
        if max_seq_int > int(until_sequence):
            return "skipped:new_messages"

        last_extracted = int(getattr(conv, "last_memory_extracted_sequence", 0) or 0)
        if last_extracted >= int(until_sequence):
            return "skipped:no_new_messages"

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.sequence > int(last_extracted))
            .where(Message.sequence <= int(until_sequence))
            .order_by(Message.sequence.asc())
            .limit(_BATCH_LIMIT)
        )
        new_messages = list(db.execute(stmt).scalars().all())
        if not new_messages:
            return "skipped:no_new_messages"

        transcript = _build_transcript(
            summary_text=getattr(conv, "summary_text", None),
            messages=new_messages,
        )
        if not transcript:
            return "skipped:empty_transcript"
        batch_last_seq = int(getattr(new_messages[-1], "sequence", 0) or 0)
        if batch_last_seq <= 0:
            return "skipped:bad_message_sequence"

        cfg = get_or_default_project_eval_config(db, project_id=UUID(str(api_key.id)))
        effective_provider_ids = get_effective_provider_ids_for_user(
            db,
            user_id=UUID(str(user.id)),
            api_key=api_key,
            provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
        )

        auth_key = _to_authenticated_api_key(api_key=api_key, user=user)

        router_model = (getattr(api_key, "kb_memory_router_logical_model", None) or "").strip()
        if not router_model:
            router_model = (getattr(api_key, "chat_title_logical_model", None) or "").strip()
        if not router_model:
            router_model = (getattr(api_key, "chat_default_logical_model", None) or "").strip() or "auto"

        embedding_model = (get_kb_global_embedding_logical_model(db) or "").strip()
        if not embedding_model:
            # Backward compatibility: allow project-level override only when not using shared strategy.
            strategy = str(getattr(settings, "qdrant_kb_user_collection_strategy", "shared") or "shared").strip().lower()
            if strategy != "shared":
                embedding_model = (getattr(api_key, "kb_embedding_logical_model", None) or "").strip()
        if not embedding_model:
            if memory_debug_logger.isEnabledFor(logging.DEBUG):
                memory_debug_logger.debug(
                    "chat_memory: skipped (conversation_id=%s user_id=%s until=%s reason=%s)",
                    str(conversation_id),
                    str(user.id),
                    int(until_sequence),
                    "kb_embedding_model_not_configured",
                )
            return "skipped:kb_embedding_model_not_configured"

        redis = get_redis_client()
        qdrant = get_qdrant_client()
        try:
            async with CurlCffiClient(timeout=60.0, impersonate="chrome120", trust_env=True) as client:
                if memory_debug_logger.isEnabledFor(logging.DEBUG):
                    memory_debug_logger.debug(
                        "chat_memory: route_start (conversation_id=%s user_id=%s cursor=%s until=%s batch_last=%s msgs=%s transcript_chars=%s router_model=%s embedding_model=%s)",
                        str(conversation_id),
                        str(user.id),
                        int(last_extracted),
                        int(until_sequence),
                        int(batch_last_seq),
                        len(new_messages),
                        len(transcript),
                        router_model,
                        embedding_model,
                    )
                decision = await route_chat_memory(
                    db,
                    redis=redis,
                    client=client,
                    api_key=auth_key,
                    effective_provider_ids=effective_provider_ids,
                    router_logical_model=router_model,
                    transcript=transcript,
                    idempotency_key=f"mem_route:{conversation_id}:{batch_last_seq}",
                )

                # Deterministic path: apply structured ops to Postgres (best-effort).
                try:
                    if getattr(decision, "structured_ops", None):
                        applied = 0
                        for op in list(decision.structured_ops or []):
                            if not isinstance(op, dict):
                                continue
                            if str(op.get("op") or "").strip().upper() != "UPSERT":
                                continue
                            sscope = str(op.get("scope") or "").strip().lower()
                            if sscope not in ("user", "project"):
                                continue
                            category = str(op.get("category") or "").strip().lower() or "config"
                            key = str(op.get("key") or "").strip()
                            if not key:
                                continue
                            value = op.get("value")
                            confidence = op.get("confidence")
                            conf: float | None = None
                            if isinstance(confidence, (int, float)):
                                conf = float(confidence)

                            if sscope == "user":
                                subject_id = make_subject_id(scope="user", user_id=UUID(str(user.id)))
                                upsert_attribute(
                                    db,
                                    subject_id=subject_id,
                                    scope="user",
                                    category=category,
                                    key=key,
                                    value=value,
                                    owner_user_id=UUID(str(user.id)),
                                    project_id=None,
                                    confidence=conf,
                                    source_conversation_id=UUID(str(conversation_id)),
                                    source_until_sequence=int(batch_last_seq),
                                )
                            else:
                                subject_id = make_subject_id(scope="project", project_id=UUID(str(api_key.id)))
                                upsert_attribute(
                                    db,
                                    subject_id=subject_id,
                                    scope="project",
                                    category=category,
                                    key=key,
                                    value=value,
                                    owner_user_id=None,
                                    project_id=UUID(str(api_key.id)),
                                    confidence=conf,
                                    source_conversation_id=UUID(str(conversation_id)),
                                    source_until_sequence=int(batch_last_seq),
                                )
                            applied += 1

                        if applied and memory_debug_logger.isEnabledFor(logging.DEBUG):
                            memory_debug_logger.debug(
                                "chat_memory: structured_ops_applied (conversation_id=%s user_id=%s batch_last=%s count=%s)",
                                str(conversation_id),
                                str(user.id),
                                int(batch_last_seq),
                                int(applied),
                            )
                except Exception:
                    # Never block main memory pipeline on structured attribute persistence.
                    if memory_debug_logger.isEnabledFor(logging.DEBUG):
                        memory_debug_logger.debug(
                            "chat_memory: structured_ops failed (conversation_id=%s user_id=%s batch_last=%s)",
                            str(conversation_id),
                            str(user.id),
                            int(batch_last_seq),
                            exc_info=True,
                        )

                if not decision.should_store or not decision.memory_text:
                    if memory_debug_logger.isEnabledFor(logging.DEBUG):
                        memory_debug_logger.debug(
                            "chat_memory: route_done (conversation_id=%s user_id=%s cursor=%s batch_last=%s until=%s should_store=%s scope=%s items=%s memory_preview=%s) -> skipped",
                            str(conversation_id),
                            str(user.id),
                            int(last_extracted),
                            int(batch_last_seq),
                            int(until_sequence),
                            bool(decision.should_store),
                            str(decision.scope),
                            len(decision.memory_items or []),
                            _preview_text(decision.memory_text, limit=160),
                        )
                    # Cursor must advance even if no memory extracted, to avoid repeated processing.
                    committed = False
                    try:
                        conv.last_memory_extracted_sequence = max(
                            int(getattr(conv, "last_memory_extracted_sequence", 0) or 0),
                            int(batch_last_seq),
                        )
                        db.add(conv)
                        db.commit()
                        committed = True
                    except Exception:
                        db.rollback()
                        committed = False

                    has_more = int(batch_last_seq) < int(until_sequence)
                    if committed:
                        if len(new_messages) >= _BATCH_LIMIT and has_more:
                            logger.info(
                                "chat_memory: batch_full requeue (conversation_id=%s user_id=%s cursor_from=%s cursor_to=%s until=%s processed=%s)",
                                str(conversation_id),
                                str(user.id),
                                int(last_extracted),
                                int(batch_last_seq),
                                int(until_sequence),
                                len(new_messages),
                                extra={"biz": "memory"},
                            )
                            _enqueue_next_batch_best_effort(
                                conversation_id=conversation_id,
                                user_id=UUID(str(user.id)),
                                until_sequence=int(until_sequence),
                            )
                        else:
                            logger.info(
                                "chat_memory: up_to_date (conversation_id=%s user_id=%s cursor_from=%s cursor_to=%s until=%s processed=%s)",
                                str(conversation_id),
                                str(user.id),
                                int(last_extracted),
                                int(batch_last_seq),
                                int(until_sequence),
                                len(new_messages),
                                extra={"biz": "memory"},
                            )
                    return "skipped:no_new_memory"

                if memory_debug_logger.isEnabledFor(logging.DEBUG):
                    memory_debug_logger.debug(
                        "chat_memory: route_done (conversation_id=%s user_id=%s cursor=%s batch_last=%s until=%s should_store=%s scope=%s items=%s memory_preview=%s)",
                        str(conversation_id),
                        str(user.id),
                        int(last_extracted),
                        int(batch_last_seq),
                        int(until_sequence),
                        bool(decision.should_store),
                        str(decision.scope),
                        len(decision.memory_items or []),
                        _preview_text(decision.memory_text, limit=160),
                    )

                vec = await embed_text(
                    db,
                    redis=redis,
                    client=client,
                    api_key=auth_key,
                    effective_provider_ids=effective_provider_ids,
                    embedding_logical_model=embedding_model,
                    text=decision.memory_text,
                    idempotency_key=f"mem_embed:{conversation_id}:{batch_last_seq}",
                )
                if not vec:
                    if memory_debug_logger.isEnabledFor(logging.DEBUG):
                        memory_debug_logger.debug(
                            "chat_memory: skipped (conversation_id=%s user_id=%s batch_last=%s until=%s reason=%s)",
                            str(conversation_id),
                            str(user.id),
                            int(batch_last_seq),
                            int(until_sequence),
                            "embedding_failed",
                        )
                    return "skipped:embedding_failed"

                if memory_debug_logger.isEnabledFor(logging.DEBUG):
                    memory_debug_logger.debug(
                        "chat_memory: embedded (conversation_id=%s user_id=%s batch_last=%s until=%s vector_dim=%s)",
                        str(conversation_id),
                        str(user.id),
                        int(batch_last_seq),
                        int(until_sequence),
                        len(vec),
                    )

                # Ensure system collection exists using the known vector size (best-effort).
                try:
                    await ensure_system_collection_ready(vector_size_hint=len(vec))
                except Exception:
                    pass

                suggested_scope = str(decision.scope or "user").strip().lower()
                target_scope = suggested_scope if suggested_scope in ("user", "system") else "user"

                if target_scope == "system":
                    collection_name = (
                        str(getattr(settings, "qdrant_kb_system_collection", "kb_system") or "kb_system").strip()
                        or "kb_system"
                    )
                    vector_size = len(vec)
                else:
                    collection_name, vector_size, _resolved_model = await ensure_collection_ready(
                        db,
                        qdrant=qdrant,
                        user_id=UUID(str(user.id)),
                        api_key=api_key,
                        preferred_model=embedding_model,
                        preferred_vector_size=len(vec),
                    )

                if int(vector_size) != len(vec):
                    return "skipped:vector_size_mismatch"

                categories: list[str] = []
                keywords: list[str] = []
                if getattr(decision, "memory_items", None):
                    for it in decision.memory_items:
                        cat = it.get("category")
                        if isinstance(cat, str) and cat.strip():
                            categories.append(cat.strip())
                        kws = it.get("keywords")
                        if isinstance(kws, list):
                            for kw in kws:
                                if isinstance(kw, str) and kw.strip():
                                    keywords.append(kw.strip())

                point_id = uuid4().hex
                payload = {
                    "scope": target_scope,
                    "owner_user_id": str(user.id) if target_scope == "user" else None,
                    "project_id": str(api_key.id) if target_scope == "user" else None,
                    # system scope is always treated as "pending approval" by default.
                    "approved": True if target_scope == "user" else False,
                    "submitted_by_user_id": str(user.id) if target_scope == "system" else None,
                    "source_type": "chat_memory_route",
                    "source_id": str(conversation_id),
                    "text": decision.memory_text,
                    "categories": categories or None,
                    "keywords": keywords or None,
                    "memory_items": decision.memory_items if getattr(decision, "memory_items", None) else None,
                    "created_at": datetime.now(UTC).isoformat(),
                    "embedding_model": str(embedding_model),
                }
                await upsert_point(
                    qdrant,
                    collection_name=collection_name,
                    point_id=point_id,
                    vector=vec,
                    payload=payload,
                    wait=True,
                )
                if memory_debug_logger.isEnabledFor(logging.DEBUG):
                    memory_debug_logger.debug(
                        "chat_memory: stored (conversation_id=%s user_id=%s batch_last=%s until=%s scope=%s collection=%s point_id=%s approved=%s vector_dim=%s)",
                        str(conversation_id),
                        str(user.id),
                        int(batch_last_seq),
                        int(until_sequence),
                        target_scope,
                        collection_name,
                        point_id,
                        bool(payload.get("approved")),
                        len(vec),
                    )
                # Advance cursor on successful processing.
                committed = False
                try:
                    conv.last_memory_extracted_sequence = max(
                        int(getattr(conv, "last_memory_extracted_sequence", 0) or 0),
                        int(batch_last_seq),
                    )
                    db.add(conv)
                    db.commit()
                    committed = True
                except Exception:
                    db.rollback()
                    committed = False

                has_more = int(batch_last_seq) < int(until_sequence)
                if committed:
                    if len(new_messages) >= _BATCH_LIMIT and has_more:
                        logger.info(
                            "chat_memory: batch_full requeue (conversation_id=%s user_id=%s cursor_from=%s cursor_to=%s until=%s processed=%s)",
                            str(conversation_id),
                            str(user.id),
                            int(last_extracted),
                            int(batch_last_seq),
                            int(until_sequence),
                            len(new_messages),
                            extra={"biz": "memory"},
                        )
                        _enqueue_next_batch_best_effort(
                            conversation_id=conversation_id,
                            user_id=UUID(str(user.id)),
                            until_sequence=int(until_sequence),
                        )
                    else:
                        logger.info(
                            "chat_memory: up_to_date (conversation_id=%s user_id=%s cursor_from=%s cursor_to=%s until=%s processed=%s)",
                            str(conversation_id),
                            str(user.id),
                            int(last_extracted),
                            int(batch_last_seq),
                            int(until_sequence),
                            len(new_messages),
                            extra={"biz": "memory"},
                        )
                return f"stored:{target_scope}"
        except QdrantNotConfigured:
            return "skipped:qdrant_not_configured"
        finally:
            await close_redis_client_for_current_loop()
            await close_qdrant_client_for_current_loop()


@shared_task(name="tasks.extract_chat_memory")
def extract_chat_memory_task(
    conversation_id: str,
    user_id: str,
    until_sequence: int,
) -> str:
    try:
        return asyncio.run(
            extract_and_store_chat_memory(
                conversation_id=UUID(str(conversation_id)),
                user_id=UUID(str(user_id)),
                until_sequence=int(until_sequence or 0),
            )
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("chat_memory task failed: %s", exc)
        return "failed"


__all__ = ["extract_and_store_chat_memory", "extract_chat_memory_task"]
