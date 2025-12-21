from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found
from app.models import Notification, NotificationReceipt, Role, UserRole
from app.schemas.notification import NotificationCreateRequest


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_user_role_codes(session: Session, user_id: UUID) -> set[str]:
    stmt: Select[tuple[str]] = (
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(session.execute(stmt).scalars().all())


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _matches_audience(
    notification: Notification,
    *,
    user_id: UUID,
    role_codes: set[str],
) -> bool:
    if notification.target_type == "all":
        return True

    if notification.target_type == "users":
        targets = set(notification.target_user_ids or [])
        return str(user_id) in targets

    if notification.target_type == "roles":
        targets = set(notification.target_role_codes or [])
        return bool(targets & role_codes)

    return False


def _filter_visible_notifications(
    notifications: Iterable[Notification],
    *,
    user_id: UUID,
    role_codes: set[str],
) -> list[Notification]:
    now = _utcnow()
    visible: list[Notification] = []
    for item in notifications:
        if not item.is_active:
            continue
        if item.expires_at is not None and item.expires_at <= now:
            continue
        if not _matches_audience(item, user_id=user_id, role_codes=role_codes):
            continue
        visible.append(item)
    return visible


def create_notification(
    session: Session,
    payload: NotificationCreateRequest,
    *,
    creator_id: UUID | None = None,
) -> Notification:
    """
    创建一条系统通知。

    - target_type=users 时必须携带 target_user_ids；
    - target_type=roles 时必须携带 target_role_codes。
    """
    creator_uuid = _as_uuid(creator_id)
    normalized_user_ids = [str(uid) for uid in payload.target_user_ids]
    normalized_roles = [code.strip() for code in payload.target_role_codes if code]

    notification = Notification(
        title=payload.title,
        content=payload.content,
        level=payload.level,
        target_type=payload.target_type,
        target_user_ids=normalized_user_ids,
        target_role_codes=normalized_roles,
        link_url=payload.link_url,
        expires_at=payload.expires_at,
        created_by=creator_uuid,
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def list_notifications_for_user(
    session: Session,
    *,
    user_id: UUID | str,
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Notification], dict[UUID, NotificationReceipt]]:
    """
    返回当前用户可见的通知及其阅读回执。
    """
    user_uuid = _as_uuid(user_id)
    role_codes = _get_user_role_codes(session, user_uuid)
    stmt: Select[tuple[Notification]] = select(Notification).order_by(
        Notification.created_at.desc()
    )
    all_items = session.execute(stmt).scalars().all()
    visible_items = _filter_visible_notifications(
        all_items,
        user_id=user_uuid,
        role_codes=role_codes,
    )

    receipt_stmt: Select[tuple[NotificationReceipt]] = select(NotificationReceipt).where(
        NotificationReceipt.user_id == user_uuid,
        NotificationReceipt.notification_id.in_([item.id for item in visible_items]),
    )
    receipts = session.execute(receipt_stmt).scalars().all()
    receipt_map: dict[UUID, NotificationReceipt] = {
        r.notification_id: r for r in receipts
    }

    if status == "unread":
        visible_items = [
            item
            for item in visible_items
            if item.id not in receipt_map or receipt_map[item.id].read_at is None
        ]

    paged = visible_items[offset : offset + limit]

    if not paged:
        return [], {}

    if status == "unread":
        receipt_map = {
            nid: receipt
            for nid, receipt in receipt_map.items()
            if receipt.read_at is None
        }

    return paged, receipt_map


def count_unread_notifications(
    session: Session,
    *,
    user_id: UUID | str,
) -> int:
    user_uuid = _as_uuid(user_id)
    role_codes = _get_user_role_codes(session, user_uuid)
    stmt: Select[tuple[Notification]] = select(Notification).order_by(
        Notification.created_at.desc()
    )
    all_items = session.execute(stmt).scalars().all()
    visible_items = _filter_visible_notifications(
        all_items, user_id=user_uuid, role_codes=role_codes
    )
    if not visible_items:
        return 0

    receipt_stmt: Select[tuple[NotificationReceipt]] = select(NotificationReceipt).where(
        NotificationReceipt.user_id == user_uuid,
        NotificationReceipt.notification_id.in_([item.id for item in visible_items]),
    )
    receipts = session.execute(receipt_stmt).scalars().all()
    receipt_map: dict[UUID, NotificationReceipt] = {
        r.notification_id: r for r in receipts
    }

    return sum(
        1
        for item in visible_items
        if item.id not in receipt_map or receipt_map[item.id].read_at is None
    )


def mark_notifications_read(
    session: Session,
    *,
    user_id: UUID | str,
    notification_ids: Sequence[UUID],
) -> int:
    """
    将指定通知标记为已读；返回成功标记的数量。
    若包含用户不可见的通知，则返回 404，避免信息泄露。
    """
    if not notification_ids:
        raise bad_request("notification_ids 不能为空")

    user_uuid = _as_uuid(user_id)

    stmt: Select[tuple[Notification]] = select(Notification).where(
        Notification.id.in_(notification_ids)
    )
    found = session.execute(stmt).scalars().all()

    role_codes = _get_user_role_codes(session, user_uuid)
    visible_map = {
        item.id: item
        for item in _filter_visible_notifications(
            found, user_id=user_uuid, role_codes=role_codes
        )
    }
    if len(visible_map) != len(set(notification_ids)):
        raise not_found("通知不存在或不可访问")

    now = _utcnow()
    updated = 0
    for notification_id in set(notification_ids):
        receipt_stmt: Select[tuple[NotificationReceipt]] = select(
            NotificationReceipt
        ).where(
            NotificationReceipt.notification_id == notification_id,
            NotificationReceipt.user_id == user_uuid,
        )
        receipt = session.execute(receipt_stmt).scalars().first()
        if receipt is None:
            receipt = NotificationReceipt(
                notification_id=notification_id,
                user_id=user_uuid,
                read_at=now,
            )
            session.add(receipt)
            updated += 1
            continue
        if receipt.read_at is None:
            receipt.read_at = now
            updated += 1

    session.commit()
    return updated


__all__ = [
    "count_unread_notifications",
    "create_notification",
    "list_notifications_for_user",
    "mark_notifications_read",
]
