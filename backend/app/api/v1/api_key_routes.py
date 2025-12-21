"""
API密钥管理路由 - V2版本，使用JWT认证而非API密钥认证
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    APIKeyAllowedProvidersRequest,
    APIKeyAllowedProvidersResponse,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
    APIKeyUpdateRequest,
)
from app.services.api_key_cache import cache_api_key_sync, invalidate_api_key_cache_sync
from app.services.api_key_provider_restriction import (
    APIKeyProviderRestrictionService,
    UnknownProviderError,
)
from app.services.api_key_service import (
    APIKeyNameAlreadyExistsError,
    create_api_key,
    delete_api_key,
    get_api_key_by_id,
    list_api_keys_for_user,
    update_api_key,
)
from app.services.user_service import get_user_by_id

router = APIRouter(
    tags=["api-keys"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_can_manage_jwt(current: AuthenticatedUser, target_user_id: UUID) -> None:
    if current.is_superuser:
        return
    if current.id != str(target_user_id):
        raise forbidden("无权管理其他用户的密钥")


def _ensure_user_exists(session: Session, user_id: UUID):
    user = get_user_by_id(session, user_id)
    if user is None:
        raise not_found(f"User {user_id} not found")
    return user


def _get_api_key_or_404(session: Session, key_id: UUID, *, user_id: UUID) -> APIKey:
    api_key = get_api_key_by_id(session, key_id, user_id=user_id)
    if api_key is None:
        raise not_found(f"API key {key_id} not found")
    return api_key


def _build_allowed_providers_response(
    api_key,
) -> APIKeyAllowedProvidersResponse:
    return APIKeyAllowedProvidersResponse(
        has_provider_restrictions=api_key.has_provider_restrictions,
        allowed_provider_ids=sorted(api_key.allowed_provider_ids),
    )


def _bad_request_for_providers(exc: UnknownProviderError):
    raise bad_request(
        "存在无效的 provider_id",
        details={"missing_provider_ids": sorted(exc.missing_ids)},
    )


@router.get(
    "/users/{user_id}/api-keys",
    response_model=list[APIKeyResponse],
)
def list_api_keys_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[APIKeyResponse]:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)

    keys = list_api_keys_for_user(db, user.id)
    return [APIKeyResponse.model_validate(item) for item in keys]


@router.post(
    "/users/{user_id}/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key_endpoint(
    user_id: UUID,
    payload: APIKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> APIKeyCreateResponse:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)

    try:
        api_key, token = create_api_key(db, user=user, payload=payload)
    except APIKeyNameAlreadyExistsError:
        raise bad_request("密钥名称已存在")
    except UnknownProviderError as exc:
        _bad_request_for_providers(exc)
    cache_api_key_sync(api_key)

    return APIKeyCreateResponse(
        **APIKeyResponse.model_validate(api_key).model_dump(),
        token=token,
    )


@router.put(
    "/users/{user_id}/api-keys/{key_id}",
    response_model=APIKeyResponse,
)
def update_api_key_endpoint(
    user_id: UUID,
    key_id: UUID,
    payload: APIKeyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> APIKeyResponse:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)

    api_key = _get_api_key_or_404(db, key_id, user_id=user.id)

    try:
        updated = update_api_key(db, api_key=api_key, payload=payload)
    except APIKeyNameAlreadyExistsError:
        raise bad_request("密钥名称已存在")
    except UnknownProviderError as exc:
        _bad_request_for_providers(exc)
    cache_api_key_sync(updated)

    return APIKeyResponse.model_validate(updated)


@router.get(
    "/users/{user_id}/api-keys/{key_id}/allowed-providers",
    response_model=APIKeyAllowedProvidersResponse,
)
def get_api_key_allowed_providers(
    user_id: UUID,
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> APIKeyAllowedProvidersResponse:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)
    api_key = _get_api_key_or_404(db, key_id, user_id=user.id)
    return _build_allowed_providers_response(api_key)


@router.put(
    "/users/{user_id}/api-keys/{key_id}/allowed-providers",
    response_model=APIKeyAllowedProvidersResponse,
)
@router.post(
    "/users/{user_id}/api-keys/{key_id}/allowed-providers",
    response_model=APIKeyAllowedProvidersResponse,
)
def set_api_key_allowed_providers(
    user_id: UUID,
    key_id: UUID,
    payload: APIKeyAllowedProvidersRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> APIKeyAllowedProvidersResponse:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)
    api_key = _get_api_key_or_404(db, key_id, user_id=user.id)

    service = APIKeyProviderRestrictionService(db)
    try:
        service.set_allowed_providers(api_key, payload.allowed_provider_ids)
        db.add(api_key)
        db.commit()
    except UnknownProviderError as exc:
        db.rollback()
        _bad_request_for_providers(exc)
    db.refresh(api_key)
    cache_api_key_sync(api_key)
    return _build_allowed_providers_response(api_key)


@router.delete(
    "/users/{user_id}/api-keys/{key_id}/allowed-providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_api_key_allowed_provider(
    user_id: UUID,
    key_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)
    api_key = _get_api_key_or_404(db, key_id, user_id=user.id)

    service = APIKeyProviderRestrictionService(db)
    current_ids = service.get_allowed_provider_ids(api_key)
    normalized_provider_id = provider_id.strip()
    if not normalized_provider_id:
        raise bad_request("provider_id 不能为空")
    if normalized_provider_id not in current_ids:
        return
    try:
        service.set_allowed_providers(
            api_key,
            [pid for pid in current_ids if pid != normalized_provider_id],
        )
        db.add(api_key)
        db.commit()
    except UnknownProviderError as exc:  # pragma: no cover - 不应触发
        db.rollback()
        _bad_request_for_providers(exc)
    db.refresh(api_key)
    cache_api_key_sync(api_key)


@router.delete(
    "/users/{user_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_api_key_endpoint(
    user_id: UUID,
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    user = _ensure_user_exists(db, user_id)
    _ensure_can_manage_jwt(current_user, user.id)

    api_key = get_api_key_by_id(db, key_id, user_id=user_id)
    if api_key is None:
        raise not_found(f"API key {key_id} not found")

    invalidate_api_key_cache_sync(api_key.key_hash)
    delete_api_key(db, api_key)


__all__ = ["router"]
