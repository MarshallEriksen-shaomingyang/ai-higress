from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DbSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.utils.response_utils import parse_json_response_body


def _extract_first_embedding_vector(payload: dict[str, Any] | None) -> list[float] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None
    item0 = data[0]
    if not isinstance(item0, dict):
        return None
    vec = item0.get("embedding")
    if not isinstance(vec, list) or not vec:
        return None
    out: list[float] = []
    for v in vec:
        if isinstance(v, (int, float)):
            out.append(float(v))
        else:
            return None
    return out


_ASYMMETRIC_MODEL_HINTS = (
    "embed-english-v3",
    "embed-multilingual-v3",
    "cohere-embed",
)
_OPENAI_EMBED_MODEL_HINTS = (
    "text-embedding-",
    "embedding-ada-002",
)


def _model_requires_input_type(model: str) -> bool:
    m = model.lower()
    return any(hint in m for hint in _ASYMMETRIC_MODEL_HINTS)


def _model_allows_input_type(model: str) -> bool:
    m = model.lower()
    # OpenAI embeddings are strict about unexpected params; skip attaching input_type for them.
    return not any(hint in m for hint in _OPENAI_EMBED_MODEL_HINTS)


async def embed_text(
    db: DbSession,
    *,
    redis: Redis,
    client: Any,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    embedding_logical_model: str,
    text: str,
    idempotency_key: str,
    input_type: str | None = None,
) -> list[float] | None:
    """
    Call upstream embeddings via the existing RequestHandler pipeline.

    This uses OpenAI-style request payload and overrides the upstream path to /v1/embeddings.
    Returns None on empty/invalid response (caller should treat it as best-effort).
    """
    model = str(embedding_logical_model or "").strip()
    if not model:
        return None

    input_text = (text or "").strip()
    if not input_text:
        return None

    # 多数 OpenAI-compatible embeddings 既支持 string 也支持 string[]；
    # 为兼容部分上游严格要求数组格式，这里统一按单元素数组发送。
    payload: dict[str, Any] = {"model": model, "input": [input_text]}
    chosen_input_type: str | None = None
    if _model_requires_input_type(model):
        chosen_input_type = (input_type or "search_document").strip().lower()
    elif input_type and _model_allows_input_type(model):
        chosen_input_type = str(input_type).strip().lower()
    if chosen_input_type:
        payload["input_type"] = chosen_input_type

    handler = RequestHandler(api_key=api_key, db=db, redis=redis, client=client)
    resp = await handler.handle(
        payload=payload,
        requested_model=model,
        lookup_model_id=model,
        api_style="openai",
        effective_provider_ids=effective_provider_ids,
        idempotency_key=idempotency_key,
        billing_reason="chat_memory_embedding",
        fallback_path_override="/v1/embeddings",
    )
    response_payload = parse_json_response_body(resp)
    return _extract_first_embedding_vector(response_payload)


__all__ = ["embed_text"]
