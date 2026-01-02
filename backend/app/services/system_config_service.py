from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

import httpx

from app.auth import AuthenticatedAPIKey
from app.models import Provider, SystemConfig
from app.qdrant_client import QdrantNotConfigured, get_qdrant_client, qdrant_is_configured
from app.services.embedding_service import embed_text
from app.settings import settings
from app.storage.qdrant_kb_store import (
    QDRANT_DEFAULT_VECTOR_NAME,
    ensure_collection_vector_size,
    get_collection_vector_size,
)


KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY = "KB_GLOBAL_EMBEDDING_LOGICAL_MODEL"


@dataclass(frozen=True)
class EffectiveConfigValue:
    key: str
    value: str | None
    source: str  # "db" | "env"


def _normalize_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _env_fallback(key: str) -> str | None:
    """
    Fallback to env/settings when DB config is missing.

    Note: For known settings keys, prefer Settings to keep a single source of truth
    for .env file parsing and type coercion.
    """
    if key == KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY:
        return _normalize_str(getattr(settings, "kb_global_embedding_logical_model", None))
    return _normalize_str(os.getenv(key))


def get_effective_config_str(db: Session, *, key: str) -> EffectiveConfigValue:
    """
    Read config from DB first, then fallback to env/settings.
    """
    k = str(key or "").strip()
    if not k:
        raise ValueError("key is required")

    stmt = select(SystemConfig).where(SystemConfig.key == k)
    row = db.execute(stmt).scalars().first()
    if row is not None:
        db_value = _normalize_str(getattr(row, "value", None))
        if db_value is not None:
            return EffectiveConfigValue(key=k, value=db_value, source="db")

    return EffectiveConfigValue(key=k, value=_env_fallback(k), source="env")


def upsert_config_str(
    db: Session,
    *,
    key: str,
    value: str | None,
    description: str | None = None,
) -> SystemConfig:
    k = str(key or "").strip()
    if not k:
        raise ValueError("key is required")

    stmt = select(SystemConfig).where(SystemConfig.key == k)
    row = db.execute(stmt).scalars().first()
    if row is None:
        row = SystemConfig(key=k)

    row.value = _normalize_str(value)
    row.value_type = "string"
    if description is not None:
        row.description = _normalize_str(description)

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_kb_global_embedding_logical_model(db: Session) -> str | None:
    return get_effective_config_str(db, key=KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY).value


def _list_all_provider_ids(db: Session) -> set[str]:
    stmt = select(Provider.provider_id)
    out: set[str] = set()
    for pid in db.execute(stmt).scalars().all():
        if isinstance(pid, str) and pid.strip():
            out.add(pid.strip())
    return out


async def validate_kb_global_embedding_model_dimension(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user_id: UUID,
    current_username: str,
    new_model: str,
) -> int:
    """
    Validate that switching the global embedding model is dimension-safe for the current KB strategy.

    Policy:
    - Only enforced when QDRANT_KB_USER_COLLECTION_STRATEGY=shared.
    - Requires Qdrant configured; otherwise reject (cannot validate).
    - Probes the embedding dimension by running a real embedding request once.
    - If shared collection exists and dimension mismatches, reject.
    - If shared collection doesn't exist yet, create it with the probed dimension.
    """
    strategy = str(getattr(settings, "qdrant_kb_user_collection_strategy", "shared") or "shared").strip().lower()
    if strategy != "shared":
        return 0

    model = _normalize_str(new_model)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="shared 策略下不允许清空全局 Embedding 模型（KB_GLOBAL_EMBEDDING_LOGICAL_MODEL）",
        )

    if not qdrant_is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Qdrant 未启用或未配置，无法进行 Embedding 维度安全校验",
        )

    providers = _list_all_provider_ids(db)
    if not providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前系统未配置任何 Provider，无法试跑 Embedding 以校验维度",
        )

    auth_key = AuthenticatedAPIKey(
        id=uuid4(),
        user_id=current_user_id,
        user_username=str(current_username or ""),
        is_superuser=True,
        name="SystemConfigAdminProbe",
        is_active=True,
        disabled_reason=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    try:
        vec = await embed_text(
            db,
            redis=redis,
            client=client,
            api_key=auth_key,
            effective_provider_ids=providers,
            embedding_logical_model=model,
            text="dimension probe",
            idempotency_key=f"syscfg:embed_dim_probe:{model}:{uuid4().hex}",
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Embedding 试跑失败（upstream status={exc.status_code}），已拒绝切换",
        ) from exc
    if not vec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding 试跑失败（上游返回空向量或响应解析失败），已拒绝切换",
        )

    dim = len(vec)
    if dim <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding 试跑返回非法维度（<=0），已拒绝切换",
        )

    shared = str(getattr(settings, "qdrant_kb_user_shared_collection", "kb_shared_v1") or "kb_shared_v1").strip()
    if not shared:
        shared = "kb_shared_v1"

    try:
        qdrant: httpx.AsyncClient = get_qdrant_client()
    except QdrantNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Qdrant 未启用或未配置，无法进行 Embedding 维度安全校验",
        )

    try:
        existing = await get_collection_vector_size(
            qdrant,
            collection_name=shared,
            vector_name=QDRANT_DEFAULT_VECTOR_NAME,
        )
        if existing is not None and int(existing) != int(dim):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"拒绝切换：新 Embedding 模型维度={dim}，但当前 Qdrant Collection({shared}) 维度={existing}"
                ),
            )

        # If collection doesn't exist, create it now to "lock in" the correct dimension.
        await ensure_collection_vector_size(
            qdrant,
            collection_name=shared,
            vector_size=int(dim),
            vector_name=QDRANT_DEFAULT_VECTOR_NAME,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant 维度校验失败：{exc!s}",
        ) from exc

    return int(dim)


__all__ = [
    "EffectiveConfigValue",
    "KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY",
    "get_effective_config_str",
    "get_kb_global_embedding_logical_model",
    "upsert_config_str",
    "validate_kb_global_embedding_model_dimension",
]
