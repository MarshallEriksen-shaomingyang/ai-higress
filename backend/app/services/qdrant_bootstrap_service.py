from __future__ import annotations

import httpx

from app.logging_config import logger
from app.qdrant_client import QdrantNotConfigured, get_qdrant_client, qdrant_is_configured
from app.settings import settings
from app.storage.qdrant_kb_store import (
    QDRANT_DEFAULT_VECTOR_NAME,
    ensure_collection_vector_size,
    get_collection_vector_size,
)


async def _try_infer_vector_size_from_any_user_collection(qdrant: httpx.AsyncClient) -> int | None:
    """
    Best-effort infer vector size from an existing user KB collection.

    This avoids requiring a manual "dimension" configuration.
    """
    strategy = str(getattr(settings, "qdrant_kb_user_collection_strategy", "shared") or "shared").strip().lower()
    if strategy == "shared":
        shared = str(getattr(settings, "qdrant_kb_user_shared_collection", "kb_shared_v1") or "kb_shared_v1").strip()
        if not shared:
            shared = "kb_shared_v1"
        try:
            size = await get_collection_vector_size(
                qdrant,
                collection_name=shared,
                vector_name=QDRANT_DEFAULT_VECTOR_NAME,
            )
            if isinstance(size, int) and size > 0:
                return int(size)
        except Exception:
            return None
        return None

    prefix = str(getattr(settings, "qdrant_kb_user_collection", "kb_user") or "kb_user").strip()
    if not prefix:
        prefix = "kb_user"
    prefix = f"{prefix}_"

    try:
        resp = await qdrant.get("/collections")
        resp.raise_for_status()
        payload = resp.json()
        cols = payload.get("result", {}).get("collections")
        if not isinstance(cols, list):
            return None
        for it in cols:
            name = None
            if isinstance(it, dict):
                name = it.get("name")
            if not isinstance(name, str) or not name:
                continue
            if not name.startswith(prefix):
                continue
            size = await get_collection_vector_size(
                qdrant,
                collection_name=name,
                vector_name=QDRANT_DEFAULT_VECTOR_NAME,
            )
            if isinstance(size, int) and size > 0:
                return int(size)
    except Exception:
        return None

    return None


async def ensure_system_collection_ready(*, vector_size_hint: int | None = None) -> bool:
    """
    Ensure system KB collection exists.

    Policy:
    - Do not require a manual "dimension" env var.
    - Prefer vector_size_hint (e.g. when we already computed an embedding).
    - Otherwise, infer size from any existing user KB collection.
    - If we still can't infer, skip (will be created later when a hint is available).
    """
    if not qdrant_is_configured():
        return False

    collection_name = str(getattr(settings, "qdrant_kb_system_collection", "kb_system") or "kb_system").strip()
    if not collection_name:
        collection_name = "kb_system"

    try:
        qdrant = get_qdrant_client()
    except QdrantNotConfigured:
        return False

    try:
        existing = await get_collection_vector_size(
            qdrant,
            collection_name=collection_name,
            vector_name=QDRANT_DEFAULT_VECTOR_NAME,
        )
        if existing is not None:
            return True

        size = int(vector_size_hint or 0) if vector_size_hint is not None else 0
        if size <= 0:
            inferred = await _try_infer_vector_size_from_any_user_collection(qdrant)
            size = int(inferred or 0)
        if size <= 0:
            logger.info(
                "qdrant_bootstrap: kb_system collection missing but vector size is unknown; defer creation"
            )
            return False

        await ensure_collection_vector_size(
            qdrant,
            collection_name=collection_name,
            vector_size=size,
            vector_name=QDRANT_DEFAULT_VECTOR_NAME,
        )
        logger.info(
            "qdrant_bootstrap: created kb_system collection=%s vector_name=%s vector_size=%d",
            collection_name,
            QDRANT_DEFAULT_VECTOR_NAME,
            size,
        )
        return True
    except Exception:
        # Startup / background bootstrap should never crash the process.
        logger.debug("qdrant_bootstrap: ensure_system_collection_ready failed", exc_info=True)
        return False


__all__ = ["ensure_system_collection_ready"]
