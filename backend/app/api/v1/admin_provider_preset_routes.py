from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    ProviderPresetCreateRequest,
    ProviderPresetExportResponse,
    ProviderPresetImportRequest,
    ProviderPresetImportResult,
    ProviderPresetResponse,
    ProviderPresetUpdateRequest,
)
from app.services.provider_preset_service import (
    ProviderPresetIdExistsError,
    ProviderPresetNotFoundError,
    create_provider_preset,
    delete_provider_preset,
    export_provider_presets,
    import_provider_presets,
    update_provider_preset,
)

router = APIRouter(
    tags=["admin-provider-presets"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


@router.post(
    "/admin/provider-presets",
    response_model=ProviderPresetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provider_preset_endpoint(
    payload: ProviderPresetCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderPresetResponse:
    _ensure_admin(current_user)
    try:
        preset = create_provider_preset(db, payload)
    except ProviderPresetIdExistsError as exc:
        raise bad_request(str(exc))
    return ProviderPresetResponse.model_validate(preset)


@router.put(
    "/admin/provider-presets/{preset_id}",
    response_model=ProviderPresetResponse,
)
def update_provider_preset_endpoint(
    preset_id: str,
    payload: ProviderPresetUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderPresetResponse:
    _ensure_admin(current_user)
    try:
        preset = update_provider_preset(db, preset_id, payload)
    except ProviderPresetNotFoundError as exc:
        raise not_found(str(exc))
    return ProviderPresetResponse.model_validate(preset)


@router.delete(
    "/admin/provider-presets/{preset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_provider_preset_endpoint(
    preset_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    _ensure_admin(current_user)
    try:
        delete_provider_preset(db, preset_id)
    except ProviderPresetNotFoundError as exc:
        raise not_found(str(exc))


@router.get(
    "/admin/provider-presets/export",
    response_model=ProviderPresetExportResponse,
)
def export_provider_presets_endpoint(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderPresetExportResponse:
    _ensure_admin(current_user)
    return export_provider_presets(db)


@router.post(
    "/admin/provider-presets/import",
    response_model=ProviderPresetImportResult,
)
def import_provider_presets_endpoint(
    payload: ProviderPresetImportRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderPresetImportResult:
    _ensure_admin(current_user)
    return import_provider_presets(db, payload)


__all__ = ["router"]
