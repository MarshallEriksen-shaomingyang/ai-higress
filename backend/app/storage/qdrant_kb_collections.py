from __future__ import annotations

import hashlib
from uuid import UUID

from app.settings import settings


def _normalize_user_id_hex(user_id: UUID | str) -> str:
    """
    Normalize user_id into a stable, collection-name-safe suffix.

    We use UUID hex (32 lowercase chars, no dashes) to avoid surprises with
    collection name validation rules across Qdrant versions.
    """
    if isinstance(user_id, UUID):
        return user_id.hex
    return UUID(str(user_id)).hex


def _normalize_user_id_uuid(user_id: UUID | str) -> UUID:
    if isinstance(user_id, UUID):
        return user_id
    return UUID(str(user_id))


def _stable_short_hash(value: str) -> str:
    """
    Build a short stable hash for collection name suffixes.

    We avoid putting raw model strings into collection names to reduce the risk
    of violating Qdrant name validation rules across versions.
    """
    raw = (value or "").strip().lower()
    if not raw:
        return "unknown"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def get_kb_system_collection_name() -> str:
    return str(getattr(settings, "qdrant_kb_system_collection", "kb_system") or "kb_system").strip()


def get_kb_user_collection_name(
    user_id: UUID | str,
    *,
    embedding_model: str | None = None,
) -> str:
    """
    User KB collection name.

    Strategy is controlled by QDRANT_KB_USER_COLLECTION_STRATEGY:
    - per_user: <QDRANT_KB_USER_COLLECTION>_<user_id_hex>
    - sharded_by_model: <QDRANT_KB_USER_COLLECTION>_<model_hash>_shard_<idx>
    """
    prefix = str(getattr(settings, "qdrant_kb_user_collection", "kb_user") or "kb_user").strip()
    if not prefix:
        prefix = "kb_user"

    strategy = str(getattr(settings, "qdrant_kb_user_collection_strategy", "per_user") or "per_user").strip().lower()
    if strategy == "shared":
        shared = str(getattr(settings, "qdrant_kb_user_shared_collection", "kb_shared_v1") or "kb_shared_v1").strip()
        return shared or "kb_shared_v1"
    if strategy == "sharded_by_model":
        shards = int(getattr(settings, "qdrant_kb_user_collection_shards", 16) or 16)
        if shards <= 0:
            raise ValueError("qdrant_kb_user_collection_shards must be positive")
        model = (embedding_model or "").strip()
        if not model:
            raise ValueError("embedding_model is required when strategy=sharded_by_model")
        model_hash = _stable_short_hash(model)
        uid = _normalize_user_id_uuid(user_id)
        shard_idx = int(uid.int % shards)
        return f"{prefix}_{model_hash}_shard_{shard_idx:04d}"

    # Default: per-user collection (physical isolation).
    return f"{prefix}_{_normalize_user_id_hex(user_id)}"


__all__ = [
    "get_kb_system_collection_name",
    "get_kb_user_collection_name",
]
