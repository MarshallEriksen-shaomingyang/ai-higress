from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_http_client, get_redis
from app.jwt_auth import AuthenticatedUser, require_superuser
from app.schemas.admin_system_config import (
    AdminSystemConfigResponse,
    AdminSystemConfigUpsertRequest,
)
from app.services.system_config_service import (
    KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY,
    get_effective_config_str,
    upsert_config_str,
    validate_kb_global_embedding_model_dimension,
)


router = APIRouter(
    prefix="/v1/admin/system/configs",
    tags=["admin-system-config"],
    dependencies=[Depends(require_superuser)],
)


@router.get("/{key}", response_model=AdminSystemConfigResponse)
def get_system_config(
    key: str,
    db: Session = Depends(get_db),
) -> AdminSystemConfigResponse:
    cfg = get_effective_config_str(db, key=key)
    return AdminSystemConfigResponse(key=cfg.key, value=cfg.value, source=cfg.source)


@router.post("", response_model=AdminSystemConfigResponse)
async def upsert_system_config(
    payload: AdminSystemConfigUpsertRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client=Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_superuser),
) -> AdminSystemConfigResponse:
    key = str(payload.key or "").strip()
    if key == KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY:
        await validate_kb_global_embedding_model_dimension(
            db,
            redis=redis,
            client=client,
            current_user_id=UUID(str(current_user.id)),
            current_username=str(current_user.username or ""),
            new_model=str(payload.value or ""),
        )

    upsert_config_str(
        db,
        key=key,
        value=payload.value,
        description=payload.description,
    )
    cfg = get_effective_config_str(db, key=key)
    return AdminSystemConfigResponse(key=cfg.key, value=cfg.value, source=cfg.source)


__all__ = ["router"]

