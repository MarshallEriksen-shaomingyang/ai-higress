from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Provider
from app.schemas import (
    AdminProviderResponse,
    AdminProvidersResponse,
    ProviderVisibilityUpdateRequest,
)

router = APIRouter(
    tags=["admin-providers"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


@router.get(
    "/admin/providers",
    response_model=AdminProvidersResponse,
)
def admin_list_providers_endpoint(
    visibility: str | None = Query(
        default=None,
        description="按可见性过滤：public/private/restricted",
    ),
    owner_id: UUID | None = Query(
        default=None,
        description="按所有者过滤（仅对 private 有意义）",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProvidersResponse:
    """管理员查看所有 Provider 列表。"""

    _ensure_admin(current_user)
    stmt: Select[tuple[Provider]] = select(Provider).order_by(Provider.created_at.desc())
    if visibility:
        stmt = stmt.where(Provider.visibility == visibility)
    if owner_id:
        stmt = stmt.where(Provider.owner_id == owner_id)
    providers = list(db.execute(stmt).scalars().all())
    return AdminProvidersResponse(
        providers=[AdminProviderResponse.model_validate(p) for p in providers],
        total=len(providers),
    )


@router.put(
    "/admin/providers/{provider_id}/visibility",
    response_model=AdminProviderResponse,
)
def update_provider_visibility_endpoint(
    provider_id: str,
    payload: ProviderVisibilityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """更新 Provider 的可见性（public/private/restricted）。"""

    _ensure_admin(current_user)
    stmt: Select[tuple[Provider]] = select(Provider).where(
        Provider.provider_id == provider_id
    )
    provider = db.execute(stmt).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")

    provider.visibility = payload.visibility
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return AdminProviderResponse.model_validate(provider)


__all__ = ["router"]

