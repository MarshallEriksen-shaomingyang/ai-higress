from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    RegistrationWindowCreateRequest,
    RegistrationWindowResponse,
)
from app.services.registration_window_service import (
    close_window_by_id,
    create_registration_window,
    get_active_registration_window,
)

router = APIRouter(
    tags=["admin-registration"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


def _create_window(
    payload: RegistrationWindowCreateRequest,
    db: Session,
    *,
    auto_activate: bool,
) -> RegistrationWindowResponse:
    try:
        window = create_registration_window(
            db,
            start_time=payload.start_time,
            end_time=payload.end_time,
            max_registrations=payload.max_registrations,
            auto_activate=auto_activate,
        )
        return RegistrationWindowResponse.model_validate(window)
    except ValueError as exc:
        raise bad_request(str(exc))


@router.post(
    "/admin/registration-windows/auto",
    response_model=RegistrationWindowResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_auto_activation_window(
    payload: RegistrationWindowCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> RegistrationWindowResponse:
    _ensure_admin(current_user)
    return _create_window(payload, db, auto_activate=True)


@router.post(
    "/admin/registration-windows/manual",
    response_model=RegistrationWindowResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_activation_window(
    payload: RegistrationWindowCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> RegistrationWindowResponse:
    _ensure_admin(current_user)
    return _create_window(payload, db, auto_activate=False)


@router.get(
    "/admin/registration-windows/active",
    response_model=RegistrationWindowResponse | None,
)
def get_active_registration_window_endpoint(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> RegistrationWindowResponse | None:
    _ensure_admin(current_user)
    window = get_active_registration_window(db)
    if window is None:
        return None
    return RegistrationWindowResponse.model_validate(window)


@router.post(
    "/admin/registration-windows/{window_id}/close",
    response_model=RegistrationWindowResponse,
)
def close_registration_window_endpoint(
    window_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> RegistrationWindowResponse:
    _ensure_admin(current_user)
    window = close_window_by_id(db, window_id)
    if window is None:
        raise not_found("指定的注册窗口不存在")
    return RegistrationWindowResponse.model_validate(window)
