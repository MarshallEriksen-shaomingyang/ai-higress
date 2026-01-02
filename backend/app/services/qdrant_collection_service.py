from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models import APIKey
from app.settings import settings
from app.services.system_config_service import get_kb_global_embedding_logical_model
from app.storage.qdrant_kb_collections import get_kb_user_collection_name
from app.storage.qdrant_kb_store import (
    QDRANT_DEFAULT_VECTOR_NAME,
    ensure_collection_vector_size,
    get_collection_vector_size,
)


async def ensure_collection_ready(
    db: Session,
    *,
    qdrant: httpx.AsyncClient,
    user_id: UUID,
    api_key: APIKey,
    preferred_model: str | None = None,
    preferred_vector_size: int | None = None,
    resolve_model_dimension: Callable[[str], Awaitable[int]] | None = None,
) -> tuple[str, int, str]:
    """
    Ensure user KB collection exists and return (collection_name, vector_size, embedding_model).

    preferred_model:
      - Explicit model (e.g. document upload ingestion)
      - When None (chat auto-memory), we pick from settings.kb_global_embedding_logical_model first,
        and fallback to api_key.kb_embedding_logical_model for backward compatibility.

    preferred_vector_size:
      - When provided, avoids probing the embedding model dimension.
    """
    global_model = str(get_kb_global_embedding_logical_model(db) or "").strip()
    project_model = str(getattr(api_key, "kb_embedding_logical_model", "") or "").strip()
    strategy = str(getattr(settings, "qdrant_kb_user_collection_strategy", "shared") or "shared").strip().lower()
    if strategy == "shared" and not global_model:
        raise RuntimeError(
            "KB_GLOBAL_EMBEDDING_LOGICAL_MODEL 未配置，但当前 QDRANT_KB_USER_COLLECTION_STRATEGY=shared；"
            "shared 策略要求全局统一 embedding 模型以保证向量维度一致"
        )
    target_model = (preferred_model or global_model or project_model).strip()
    if not target_model:
        raise RuntimeError("kb_embedding_logical_model 未配置，无法初始化用户知识库 collection")

    if preferred_vector_size is not None:
        target_dim = int(preferred_vector_size)
        if target_dim <= 0:
            raise ValueError("preferred_vector_size must be positive")
    else:
        if resolve_model_dimension is None:
            raise RuntimeError("resolve_model_dimension is required when preferred_vector_size is not provided")
        target_dim = int(await resolve_model_dimension(target_model))
        if target_dim <= 0:
            raise RuntimeError("resolved embedding dimension must be positive")

    collection_name = get_kb_user_collection_name(user_id, embedding_model=target_model)

    existing_size = await get_collection_vector_size(
        qdrant,
        collection_name=collection_name,
        vector_name=QDRANT_DEFAULT_VECTOR_NAME,
    )
    if existing_size is not None:
        return collection_name, int(existing_size), target_model

    await ensure_collection_vector_size(
        qdrant,
        collection_name=collection_name,
        vector_size=target_dim,
        vector_name=QDRANT_DEFAULT_VECTOR_NAME,
    )

    return collection_name, target_dim, target_model


__all__ = ["ensure_collection_ready"]
