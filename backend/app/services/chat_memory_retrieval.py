from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.auth import AuthenticatedAPIKey
from app.qdrant_client import QdrantNotConfigured, get_qdrant_client, qdrant_is_configured
from app.settings import settings
from app.services.embedding_service import embed_text
from app.storage.qdrant_kb_collections import get_kb_user_collection_name
from app.storage.qdrant_kb_store import QDRANT_DEFAULT_VECTOR_NAME, search_points


memory_debug_logger = logging.getLogger("apiproxy.memory_debug")

_MEMORY_HINT_RE = re.compile(
    r"(记得|记住|别忘|之前|上次|以前|你说过|我说过|还记得|回忆|偏好|习惯|约定|按之前|照之前)",
    re.IGNORECASE,
)
_PRONOUN_RE = re.compile(r"(它|那个|这(个|里|段)|上面|前面|刚才|之前那个)", re.IGNORECASE)


def should_retrieve_user_memory(user_text: str) -> bool:
    text = (user_text or "").strip()
    if not text:
        return False
    if len(text) >= 120:
        # Long requests often benefit from retrieving preferences/project context.
        return True
    return bool(_MEMORY_HINT_RE.search(text))


def build_retrieval_query(*, user_text: str, summary_text: str | None) -> str:
    """
    Build an embedding query without invoking an extra LLM rewrite (MVP).

    Heuristic:
    - If user text contains pronouns / is short, prepend conversation summary for disambiguation.
    """
    text = (user_text or "").strip()
    summary = (summary_text or "").strip()
    if not text:
        return ""
    if summary and (len(text) < 40 or _PRONOUN_RE.search(text)):
        return f"Conversation summary:\n{summary}\n\nUser query:\n{text}".strip()
    return text


def inject_memory_context_into_messages(
    messages: list[dict[str, Any]],
    *,
    memory_context: str,
) -> list[dict[str, Any]]:
    ctx = (memory_context or "").strip()
    if not ctx:
        return messages
    if not isinstance(messages, list) or not messages:
        return [{"role": "system", "content": ctx}]

    # Insert after initial system messages (system_prompt + conversation summary).
    idx = 0
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "system":
            idx += 1
        else:
            break
    injected = list(messages)
    injected.insert(idx, {"role": "system", "content": ctx})
    return injected


def _truncate_text(value: str | None, *, limit: int = 800) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _format_retrieved_payloads(payloads: list[dict[str, Any]], *, limit: int) -> str:
    if not payloads:
        return ""
    lines: list[str] = []
    for it in payloads[: max(1, int(limit or 0))]:
        if not isinstance(it, dict):
            continue
        text = it.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        cats = it.get("categories")
        cat_label = ""
        if isinstance(cats, list):
            parts = [c.strip() for c in cats if isinstance(c, str) and c.strip()]
            if parts:
                cat_label = f"[{','.join(parts[:3])}] "
        lines.append(f"- {cat_label}{_truncate_text(text, limit=320)}")
    if not lines:
        return ""
    header = "以下为检索到的用户长期记忆（仅供参考，可能过期；如与当前问题无关请忽略）："
    return "\n".join([header, *lines]).strip()


def _build_secure_user_memory_filter(*, owner_user_id: UUID, project_id: UUID) -> dict[str, Any]:
    # Mandatory isolation filter: never allow caller to bypass.
    return {
        "must": [
            {"key": "scope", "match": {"value": "user"}},
            {"key": "approved", "match": {"value": True}},
            {"key": "owner_user_id", "match": {"value": str(owner_user_id)}},
            {"key": "project_id", "match": {"value": str(project_id)}},
        ]
    }


async def maybe_retrieve_user_memory_context(
    db: DbSession,
    *,
    redis: Redis,
    client: Any,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    owner_user_id: UUID,
    project_id: UUID,
    user_text: str,
    summary_text: str | None,
    top_k: int = 3,
    idempotency_key: str,
) -> str:
    """
    Best-effort memory retrieval (read path).

    Returns a system-message content string to be injected into the prompt,
    or empty string if retrieval is skipped/failed.
    """
    if not qdrant_is_configured():
        return ""

    if not should_retrieve_user_memory(user_text):
        return ""

    embedding_model = str(getattr(settings, "kb_global_embedding_logical_model", "") or "").strip()
    if not embedding_model:
        # MVP expects global embedding; fallback to project-level only when global is not set.
        return ""

    query = build_retrieval_query(user_text=user_text, summary_text=summary_text)
    if not query:
        return ""

    try:
        qdrant = get_qdrant_client()
    except QdrantNotConfigured:
        return ""

    try:
        vec = await embed_text(
            db,
            redis=redis,
            client=client,
            api_key=api_key,
            effective_provider_ids=effective_provider_ids,
            embedding_logical_model=embedding_model,
            text=query,
            idempotency_key=idempotency_key,
        )
        if not vec:
            return ""

        collection_name = get_kb_user_collection_name(owner_user_id, embedding_model=embedding_model)
        qfilter = _build_secure_user_memory_filter(owner_user_id=owner_user_id, project_id=project_id)
        hits = await search_points(
            qdrant,
            collection_name=collection_name,
            vector=vec,
            limit=max(1, min(int(top_k or 0), 10)),
            query_filter=qfilter,
            vector_name=QDRANT_DEFAULT_VECTOR_NAME,
        )
        payloads: list[dict[str, Any]] = []
        for h in hits:
            if isinstance(h, dict):
                p = h.get("payload")
                if isinstance(p, dict):
                    payloads.append(p)

        ctx = _format_retrieved_payloads(payloads, limit=top_k)
        if memory_debug_logger.isEnabledFor(logging.DEBUG):
            memory_debug_logger.debug(
                "memory_retrieval: done (user_id=%s project_id=%s should=%s query_chars=%s dim=%s hits=%s)",
                str(owner_user_id),
                str(project_id),
                True,
                len(query),
                len(vec),
                len(payloads),
            )
        return ctx
    except Exception:
        if memory_debug_logger.isEnabledFor(logging.DEBUG):
            memory_debug_logger.debug(
                "memory_retrieval: failed (user_id=%s project_id=%s)", str(owner_user_id), str(project_id), exc_info=True
            )
        return ""


__all__ = [
    "build_retrieval_query",
    "inject_memory_context_into_messages",
    "maybe_retrieve_user_memory_context",
    "should_retrieve_user_memory",
]
