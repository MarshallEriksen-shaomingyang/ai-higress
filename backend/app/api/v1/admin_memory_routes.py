from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedAPIKey
from app.deps import get_db, get_http_client, get_qdrant, get_redis
from app.jwt_auth import AuthenticatedUser, require_superuser
from app.schemas.admin_memory import (
    AdminMemoryApproveRequest,
    AdminMemoryCreateRequest,
    AdminMemoryItemResponse,
    AdminMemoryListResponse,
)
from app.settings import settings
from app.services.embedding_service import embed_text
from app.services.api_key_service import get_api_key_by_id
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
)
from app.services.qdrant_bootstrap_service import ensure_system_collection_ready
from app.services.system_config_service import get_kb_global_embedding_logical_model
from app.storage.qdrant_kb_store import (
    delete_points,
    scroll_points,
    search_points,
    upsert_point,
)


router = APIRouter(prefix="/v1/admin/memories", tags=["admin-memory"], dependencies=[Depends(require_superuser)])
logger = logging.getLogger(__name__)


def _get_system_collection_name() -> str:
    return str(getattr(settings, "qdrant_kb_system_collection", "kb_system") or "kb_system")


async def _get_embedding_vector(
    db: Session,
    redis,
    client,
    text: str,
    current_user: AuthenticatedUser,
    project_id: UUID,
) -> list[float]:
    embedding_model = str(get_kb_global_embedding_logical_model(db) or "").strip()
    if not embedding_model:
        # Fallback logic mirroring tasks.chat_memory: try to infer from project or just fail
        # Since this is admin interface for system memory, we really need the global model.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="KB_GLOBAL_EMBEDDING_LOGICAL_MODEL not configured. System memory requires a global embedding model.",
        )

    # We need an AuthenticatedAPIKey for RequestHandler. 
    # Since this is admin operating, we can create a synthetic one or look up admin's key.
    # For simplicity, we synthesize one representing the admin user.
    from app.models import User
    
    admin_user = db.get(User, UUID(str(current_user.id)))
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    api_key = get_api_key_by_id(db, project_id, user_id=UUID(str(admin_user.id)))
    if api_key is None or not bool(getattr(api_key, "is_active", False)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project API Key not found or inactive")

    cfg = get_or_default_project_eval_config(db, project_id=UUID(str(api_key.id)))
    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(admin_user.id)),
        api_key=api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )
    
    auth_key = AuthenticatedAPIKey(
        id=UUID(str(api_key.id)),
        user_id=UUID(str(api_key.user_id)),
        user_username=str(admin_user.username or ""),
        is_superuser=True,
        name="AdminOps",
        is_active=True,
        disabled_reason=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )

    vec = await embed_text(
        db,
        redis=redis,
        client=client,
        api_key=auth_key,
        effective_provider_ids=effective_provider_ids,
        embedding_logical_model=embedding_model,
        text=text,
        idempotency_key=f"admin_embed:{uuid4()}",
    )
    
    if not vec:
        raise HTTPException(status_code=500, detail="Embedding failed (upstream returned empty)")
    
    return vec


@router.get("/candidates", response_model=AdminMemoryListResponse)
async def list_candidates(
    limit: int = Query(20, ge=1, le=100),
    offset: str | None = Query(None),
    qdrant=Depends(get_qdrant),
):
    """
    List pending system memory candidates (scope=system, approved=false).
    These are typically auto-extracted by AI from user conversations.
    """
    collection_name = _get_system_collection_name()
    
    query_filter = {
        "must": [
            {"key": "scope", "match": {"value": "system"}},
            {"key": "approved", "match": {"value": False}},
        ]
    }
    
    points, next_offset = await scroll_points(
        qdrant,
        collection_name=collection_name,
        limit=limit,
        query_filter=query_filter,
        offset=offset,
        with_payload=True,
    )
    
    items = []
    for p in points:
        payload = p.get("payload", {})
        items.append(
            AdminMemoryItemResponse(
                id=str(p["id"]),
                content=payload.get("text") or "",
                categories=payload.get("categories"),
                keywords=payload.get("keywords"),
                created_at=payload.get("created_at"),
                scope=payload.get("scope", "system"),
                approved=bool(payload.get("approved", False)),
                submitted_by_user_id=payload.get("submitted_by_user_id"),
                source_id=payload.get("source_id"),
            )
        )
        
    return AdminMemoryListResponse(items=items, next_offset=str(next_offset) if next_offset else None)


@router.get("/published", response_model=AdminMemoryListResponse)
async def list_published(
    limit: int = Query(20, ge=1, le=100),
    offset: str | None = Query(None),
    qdrant=Depends(get_qdrant),
):
    """
    List active system memories (scope=system, approved=true).
    """
    collection_name = _get_system_collection_name()
    
    query_filter = {
        "must": [
            {"key": "scope", "match": {"value": "system"}},
            {"key": "approved", "match": {"value": True}},
        ]
    }
    
    points, next_offset = await scroll_points(
        qdrant,
        collection_name=collection_name,
        limit=limit,
        query_filter=query_filter,
        offset=offset,
        with_payload=True,
    )
    
    items = []
    for p in points:
        payload = p.get("payload", {})
        items.append(
            AdminMemoryItemResponse(
                id=str(p["id"]),
                content=payload.get("text") or "",
                categories=payload.get("categories"),
                keywords=payload.get("keywords"),
                created_at=payload.get("created_at"),
                scope=payload.get("scope", "system"),
                approved=bool(payload.get("approved", True)),
                submitted_by_user_id=payload.get("submitted_by_user_id"),
                source_id=payload.get("source_id"),
            )
        )
        
    return AdminMemoryListResponse(items=items, next_offset=str(next_offset) if next_offset else None)


@router.post("/{point_id}/approve", response_model=AdminMemoryItemResponse)
async def approve_candidate(
    point_id: str,
    payload: AdminMemoryApproveRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    client=Depends(get_http_client),
    qdrant=Depends(get_qdrant),
    current_user: AuthenticatedUser = Depends(require_superuser),
):
    """
    Approve a system memory candidate.
    
    If content is modified, re-embedding is triggered.
    Sets approved=True.
    """
    collection_name = _get_system_collection_name()
    
    # 1. Fetch original point
    # We use search by ID via scroll filter since retrieve by ID isn't exposed in our store wrapper yet
    # Or just use qdrant client directly for get
    try:
        resp = await qdrant.get(f"/collections/{collection_name}/points/{point_id}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Memory item not found")
        resp.raise_for_status()
        point_data = resp.json().get("result")
    except Exception as e:
        logger.error(f"Failed to fetch point {point_id}: {e}")
        raise HTTPException(status_code=500, detail="Storage error")

    if not point_data:
        raise HTTPException(status_code=404, detail="Memory item not found")
        
    current_payload = point_data.get("payload", {})
    
    # 2. Update fields
    new_text = payload.content.strip() if payload.content else current_payload.get("text", "")
    new_categories = payload.categories if payload.categories is not None else current_payload.get("categories")
    new_keywords = payload.keywords if payload.keywords is not None else current_payload.get("keywords")
    
    # 3. Re-embed if text changed
    vec = point_data.get("vector")
    # Some qdrant configs return vector separately or not at all depending on params.
    # If text changed, we MUST re-embed.
    text_changed = new_text != current_payload.get("text", "")
    
    if text_changed or not vec:
        vec = await _get_embedding_vector(db, redis, client, new_text, current_user, payload.project_id)
        
    # 4. Upsert with approved=True
    updated_payload = current_payload.copy()
    updated_payload["text"] = new_text
    updated_payload["categories"] = new_categories
    updated_payload["keywords"] = new_keywords
    updated_payload["approved"] = True
    updated_payload["updated_at"] = datetime.now(UTC).isoformat()
    updated_payload["approved_by_user_id"] = str(current_user.id)
    
    await upsert_point(
        qdrant,
        collection_name=collection_name,
        point_id=point_id,
        vector=vec,
        payload=updated_payload,
        wait=True
    )
    
    return AdminMemoryItemResponse(
        id=point_id,
        content=new_text,
        categories=new_categories,
        keywords=new_keywords,
        created_at=updated_payload.get("created_at"),
        scope=updated_payload.get("scope", "system"),
        approved=True,
        submitted_by_user_id=updated_payload.get("submitted_by_user_id"),
        source_id=updated_payload.get("source_id"),
    )


@router.post("", response_model=AdminMemoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_system_memory(
    payload: AdminMemoryCreateRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    client=Depends(get_http_client),
    qdrant=Depends(get_qdrant),
    current_user: AuthenticatedUser = Depends(require_superuser),
):
    """
    Manually create a published system memory.
    """
    collection_name = _get_system_collection_name()

    # 1. Embed
    vec = await _get_embedding_vector(db, redis, client, payload.content, current_user, payload.project_id)

    # Ensure system collection exists using the known vector size (best-effort).
    try:
        await ensure_system_collection_ready(vector_size_hint=len(vec))
    except Exception:
        pass
    
    # 2. Upsert
    point_id = uuid4().hex
    
    data = {
        "scope": "system",
        "owner_user_id": None,
        "project_id": None,
        "approved": True,
        "submitted_by_user_id": str(current_user.id),
        "source_type": "admin_manual",
        "text": payload.content,
        "categories": payload.categories,
        "keywords": payload.keywords,
        "created_at": datetime.now(UTC).isoformat(),
        "embedding_model": str(get_kb_global_embedding_logical_model(db) or "unknown"),
    }
    
    await upsert_point(
        qdrant,
        collection_name=collection_name,
        point_id=point_id,
        vector=vec,
        payload=data,
        wait=True
    )
    
    return AdminMemoryItemResponse(
        id=point_id,
        content=data["text"],
        categories=data["categories"],
        keywords=data["keywords"],
        created_at=data["created_at"],
        scope="system",
        approved=True,
        submitted_by_user_id=data["submitted_by_user_id"],
        source_id=None,
    )


@router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_memory(
    point_id: str,
    qdrant=Depends(get_qdrant),
    current_user: AuthenticatedUser = Depends(require_superuser),
):
    """
    Delete a system memory (whether candidate or published).
    """
    collection_name = _get_system_collection_name()
    
    # We restrict this to system scope just to be safe, 
    # though ID collision with user collection isn't possible (diff collections).
    # But qdrant delete by ID in a specific collection is safe enough.
    
    await delete_points(
        qdrant,
        collection_name=collection_name,
        points_ids=[point_id],
        wait=True
    )
