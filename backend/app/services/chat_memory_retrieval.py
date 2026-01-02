from __future__ import annotations

import datetime as dt
import logging
import re
import time
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.qdrant_client import QdrantNotConfigured, get_qdrant_client, qdrant_is_configured
from app.settings import settings
from app.services.embedding_service import embed_text
from app.services.memory_metrics_buffer import get_memory_metrics_recorder
from app.services.system_config_service import get_kb_global_embedding_logical_model
from app.storage.qdrant_kb_collections import get_kb_user_collection_name
from app.storage.qdrant_kb_store import QDRANT_DEFAULT_VECTOR_NAME, search_points
from app.utils.response_utils import extract_first_choice_text, parse_json_response_body


memory_debug_logger = logging.getLogger("apiproxy.memory_debug")

_MEMORY_HINT_RE = re.compile(
    r"(记得|记住|别忘|之前|上次|以前|你说过|我说过|还记得|回忆|偏好|习惯|约定|按之前|照之前)",
    re.IGNORECASE,
)
_PRONOUN_RE = re.compile(r"(它|那个|这(个|里|段)|上面|前面|刚才|之前那个)", re.IGNORECASE)

_REWRITE_SYSTEM_PROMPT = (
    "Role: Query Rewriter\n"
    "Goal: Resolve pronouns and implicit references in the user's latest query based on conversation history, "
    "outputting a standalone search query for a vector database.\n"
    "\n"
    "Rules:\n"
    "1. If the query contains pronouns (e.g., 'it', 'that', 'he', 'previous one'), replace them with specific entities from history.\n"
    "2. If the query depends on context (e.g., 'how about Python?'), add the missing context.\n"
    "3. Remove conversational fillers (e.g., 'please', 'hello', 'can you tell me').\n"
    "4. If the query is already self-contained, output it as is.\n"
    "5. Output ONLY the rewritten query string. No explanations.\n"
)


async def rewrite_search_query(
    db: DbSession,
    *,
    redis: Redis,
    client: Any,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    router_logical_model: str,
    user_text: str,
    summary_text: str | None,
    idempotency_key: str,
) -> str:
    """
    Use an LLM to rewrite the user query into a standalone search query.
    """
    model = str(router_logical_model or "").strip()
    if not model:
        return user_text

    text = (user_text or "").strip()
    if not text:
        return ""

    # Context construction: summary + last user query.
    # We don't send full history to save tokens/latency for this lightweight task.
    context_str = ""
    if summary_text:
        context_str = f"Conversation Summary:\n{summary_text}\n\n"

    user_content = f"{context_str}Latest User Query:\n{text}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 128,
    }

    try:
        handler = RequestHandler(api_key=api_key, db=db, redis=redis, client=client)
        resp = await handler.handle(
            payload=payload,
            requested_model=model,
            lookup_model_id=model,
            api_style="openai",
            effective_provider_ids=effective_provider_ids,
            idempotency_key=idempotency_key,
            billing_reason="chat_memory_rewrite",
        )
        response_payload = parse_json_response_body(resp)
        rewritten = (extract_first_choice_text(response_payload) or "").strip()
        # Fallback if model outputs nothing or hallucinated empty string
        if not rewritten:
            return text
        return rewritten
    except Exception:
        # Fallback to original text on any error to ensure resilience
        if memory_debug_logger.isEnabledFor(logging.DEBUG):
            memory_debug_logger.debug("memory_rewrite: failed, fallback to original", exc_info=True)
        return text


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
    # Metrics tracking
    start_time = time.perf_counter()
    window_start = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    recorder = get_memory_metrics_recorder()

    def _record_metrics(
        triggered: bool,
        success: bool | None,
        raw_hits: int = 0,
        valid_hits: int = 0,
    ) -> None:
        latency_ms = (time.perf_counter() - start_time) * 1000
        recorder.record_retrieval(
            user_id=owner_user_id,
            project_id=project_id,
            window_start=window_start,
            triggered=triggered,
            success=success,
            latency_ms=latency_ms,
            raw_hits=raw_hits,
            valid_hits=valid_hits,
        )

    if not qdrant_is_configured():
        _record_metrics(triggered=False, success=None)
        return ""

    if not should_retrieve_user_memory(user_text):
        _record_metrics(triggered=False, success=None)
        return ""

    embedding_model = str(get_kb_global_embedding_logical_model(db) or "").strip()
    if not embedding_model:
        # MVP expects global embedding; fallback to project-level only when global is not set.
        _record_metrics(triggered=False, success=None)
        return ""

    query = build_retrieval_query(user_text=user_text, summary_text=summary_text)

    # 2. Enhanced Rewriting (LLM-based)
    # Trigger condition: Heuristic detected pronouns OR short query with summary context available.
    # We reuse the project's configured router model (often a cheaper/faster model).
    router_model = (getattr(api_key, "kb_memory_router_logical_model", None) or "").strip()
    # Also fallback to chat_title_logical_model if router not set, as it's usually cheap.
    if not router_model:
        router_model = (getattr(api_key, "chat_title_logical_model", None) or "").strip()

    should_rewrite = bool(router_model and (_PRONOUN_RE.search(user_text) or (summary_text and len(user_text) < 20)))

    if should_rewrite:
        rewrite_start = time.perf_counter()
        rewritten = await rewrite_search_query(
            db,
            redis=redis,
            client=client,
            api_key=api_key,
            effective_provider_ids=effective_provider_ids,
            router_logical_model=router_model,
            user_text=user_text,
            summary_text=summary_text,
            idempotency_key=f"{idempotency_key}:rewrite",
        )
        rewrite_latency_ms = (time.perf_counter() - rewrite_start) * 1000
        recorder.record_rewrite(
            user_id=owner_user_id,
            project_id=project_id,
            window_start=window_start,
            triggered=True,
            success=bool(rewritten and rewritten != user_text),
            latency_ms=rewrite_latency_ms,
        )
        if rewritten:
            query = rewritten

    if not query:
        _record_metrics(triggered=True, success=False)
        return ""

    try:
        qdrant = get_qdrant_client()
    except QdrantNotConfigured:
        _record_metrics(triggered=True, success=None)
        return ""

    try:
        embed_start = time.perf_counter()
        vec = await embed_text(
            db,
            redis=redis,
            client=client,
            api_key=api_key,
            effective_provider_ids=effective_provider_ids,
            embedding_logical_model=embedding_model,
            text=query,
            idempotency_key=idempotency_key,
            input_type="search_query",
        )
        embed_latency_ms = (time.perf_counter() - embed_start) * 1000
        recorder.record_embedding(
            user_id=owner_user_id,
            project_id=project_id,
            window_start=window_start,
            latency_ms=embed_latency_ms,
        )

        if not vec:
            _record_metrics(triggered=True, success=False)
            return ""

        collection_name = get_kb_user_collection_name(owner_user_id, embedding_model=embedding_model)
        qfilter = _build_secure_user_memory_filter(owner_user_id=owner_user_id, project_id=project_id)

        # 3. Dynamic Retrieval (Top-K + Score Threshold)
        # We ask for a bit more candidates (limit=10) to allow for score filtering and deduplication.
        raw_hits = await search_points(
            qdrant,
            collection_name=collection_name,
            vector=vec,
            limit=10,
            query_filter=qfilter,
            vector_name=QDRANT_DEFAULT_VECTOR_NAME,
        )

        # Minimum score to be considered relevant (0.0-1.0 cosine similarity)
        # TODO: Move to project config
        MIN_SCORE_THRESHOLD = 0.75

        valid_hits = []
        seen_content_hashes = set()

        for h in raw_hits:
            if not isinstance(h, dict):
                continue

            score = h.get("score")
            # If score is available and too low, skip
            if isinstance(score, (int, float)) and score < MIN_SCORE_THRESHOLD:
                continue

            p = h.get("payload")
            if not isinstance(p, dict):
                continue

            text = (p.get("text") or "").strip()
            if not text:
                continue

            # Deduplication: simple exact match or very short content collision
            # For more advanced dedup, we could use MinHash or just Levenshtein, but exact match is a safe start.
            # We also dedupe based on ID just in case.
            pid = str(h.get("id"))
            if pid in seen_content_hashes:
                continue

            # Content-based hash (simple)
            content_hash = hash(text[:128]) # Optimization: only hash prefix
            if content_hash in seen_content_hashes:
                continue

            seen_content_hashes.add(pid)
            seen_content_hashes.add(content_hash)

            valid_hits.append(p)

            # Dynamic Top-K: stop if we have enough high-quality hits
            if len(valid_hits) >= top_k:
                break

        ctx = _format_retrieved_payloads(valid_hits, limit=top_k)

        # Record metrics with hit/miss info
        _record_metrics(
            triggered=True,
            success=len(valid_hits) > 0,
            raw_hits=len(raw_hits),
            valid_hits=len(valid_hits),
        )

        if memory_debug_logger.isEnabledFor(logging.DEBUG):
            memory_debug_logger.debug(
                "memory_retrieval: done (user_id=%s project_id=%s should=%s rewritten=%s query_chars=%s dim=%s raw_hits=%s valid_hits=%s)",
                str(owner_user_id),
                str(project_id),
                True,
                should_rewrite,
                len(query),
                len(vec),
                len(raw_hits),
                len(valid_hits),
            )
        return ctx
    except Exception:
        _record_metrics(triggered=True, success=None)
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
