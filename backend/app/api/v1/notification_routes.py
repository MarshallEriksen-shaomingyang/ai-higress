from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification_service import (
    count_unread_notifications,
    list_notifications_for_user,
    mark_notifications_read,
)

router = APIRouter(tags=["notifications"], prefix="/v1/notifications")


def _build_response(
    notification,
    receipt_map,
) -> NotificationResponse:
    receipt = receipt_map.get(notification.id)
    return NotificationResponse(
        id=notification.id,
        title=notification.title,
        content=notification.content,
        level=notification.level,
        target_type=notification.target_type,
        target_user_ids=[UUID(str(uid)) for uid in notification.target_user_ids or []],
        target_role_codes=notification.target_role_codes or [],
        link_url=notification.link_url,
        expires_at=notification.expires_at,
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        created_by=notification.created_by,
        is_read=receipt.read_at is not None if receipt else False,
        read_at=receipt.read_at if receipt else None,
    )


@router.get("", response_model=list[NotificationResponse])
def list_my_notifications(
    status_filter: str = Query(
        "all", pattern="^(all|unread)$", description="all 或 unread"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[NotificationResponse]:
    """
    列出当前用户可见的通知。
    """
    notifications, receipts = list_notifications_for_user(
        db,
        user_id=current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_build_response(item, receipts) for item in notifications]


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UnreadCountResponse:
    """
    返回当前用户的未读通知数量。
    """
    count = count_unread_notifications(db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.post(
    "/read",
    response_model=NotificationMarkReadResponse,
    status_code=status.HTTP_200_OK,
)
def mark_notifications_as_read(
    payload: NotificationMarkReadRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> NotificationMarkReadResponse:
    """
    将指定通知标记为已读。
    """
    updated = mark_notifications_read(
        db, user_id=current_user.id, notification_ids=payload.notification_ids
    )
    return NotificationMarkReadResponse(updated_count=updated)


__all__ = ["router"]
