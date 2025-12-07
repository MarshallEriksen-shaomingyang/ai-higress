from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import forbidden
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Notification
from app.schemas import (
    NotificationAdminResponse,
    NotificationCreateRequest,
)
from app.services.notification_service import create_notification

router = APIRouter(
    tags=["admin-notifications"],
    prefix="/v1/admin/notifications",
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


@router.post(
    "",
    response_model=NotificationAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_notification(
    payload: NotificationCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> NotificationAdminResponse:
    """
    管理员创建公告/通知。
    """
    _ensure_admin(current_user)
    notification = create_notification(
        db, payload, creator_id=current_user.id
    )
    return NotificationAdminResponse.model_validate(notification)


@router.get("", response_model=list[NotificationAdminResponse])
def list_admin_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[NotificationAdminResponse]:
    """
    管理员查看已发布的通知（按创建时间倒序）。
    """
    _ensure_admin(current_user)
    stmt: Select[tuple[Notification]] = (
        select(Notification)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = db.execute(stmt).scalars().all()
    return [NotificationAdminResponse.model_validate(item) for item in items]


__all__ = ["router"]
