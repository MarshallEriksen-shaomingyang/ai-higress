from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Provider, ProviderAPIKey, ProviderSubmission
from app.schemas.notification import NotificationCreateRequest
from app.schemas.provider_control import (
    ProviderReviewRequest,
    ProviderSubmissionRequest,
)
from app.services.encryption import encrypt_secret
from app.services.notification_service import create_notification


class ProviderSubmissionServiceError(RuntimeError):
    """Base error for provider submission operations."""


class ProviderSubmissionNotFoundError(ProviderSubmissionServiceError):
    """Raised when a submission is not found."""


def create_submission(
    session: Session,
    user_id: UUID,
    payload: ProviderSubmissionRequest,
    metadata: dict | None = None,
) -> ProviderSubmission:
    """创建一条共享提供商提交记录。

    注意：此函数不会立即创建 Provider，仅保存提交与加密后的 API Key。
    """

    encrypted_config: str | None = None
    if payload.extra_config is not None:
        # 目前直接存为 JSON 字符串，后续可接入统一加密方案。
        import json

        encrypted_config = json.dumps(payload.extra_config, ensure_ascii=False)

    encrypted_api_key = None
    if payload.api_key:
        encrypted_api_key = encrypt_secret(payload.api_key)

    submission = ProviderSubmission(
        user_id=user_id,
        name=payload.name,
        provider_id=payload.provider_id,
        base_url=str(payload.base_url),
        provider_type=payload.provider_type or "native",
        encrypted_config=encrypted_config,
        encrypted_api_key=encrypted_api_key,
        description=payload.description,
        approval_status="pending",
    )

    session.add(submission)
    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover - 并发保护
        session.rollback()
        logger.error("Failed to create provider submission: %s", exc)
        raise ProviderSubmissionServiceError("无法创建提供商提交记录") from exc
    session.refresh(submission)

    # 通知提交者已进入审核
    try:
        create_notification(
            session,
            NotificationCreateRequest(
                title="共享提供商提交已创建",
                content=f"提交 {submission.name} 已进入审核流程。",
                level="info",
                target_type="users",
                target_user_ids=[user_id],
            ),
            creator_id=user_id,
        )
    except Exception:  # pragma: no cover - 通知失败不影响主流程
        logger.exception(
            "Failed to send notification for submission %s creation", submission.id
        )
    return submission


def list_submissions(
    session: Session,
    status: Optional[str] = None,
) -> List[ProviderSubmission]:
    """按可选状态过滤列出提交记录。"""
    stmt: Select[tuple[ProviderSubmission]] = select(ProviderSubmission).order_by(
        ProviderSubmission.created_at.desc()
    )
    if status:
        stmt = stmt.where(ProviderSubmission.approval_status == status)
    return list(session.execute(stmt).scalars().all())


def list_user_submissions(
    session: Session,
    user_id: UUID,
    status: Optional[str] = None,
) -> List[ProviderSubmission]:
    """按用户和可选状态过滤列出提交记录。"""
    stmt: Select[tuple[ProviderSubmission]] = (
        select(ProviderSubmission)
        .where(ProviderSubmission.user_id == user_id)
        .order_by(ProviderSubmission.created_at.desc())
    )
    if status:
        stmt = stmt.where(ProviderSubmission.approval_status == status)
    return list(session.execute(stmt).scalars().all())


def get_submission(session: Session, submission_id: UUID) -> Optional[ProviderSubmission]:
    return session.get(ProviderSubmission, submission_id)


def approve_submission(
    session: Session,
    submission_id: UUID,
    reviewer_id: UUID,
    review_notes: str | None = None,
) -> Provider:
    """审核通过一个提交并创建对应的公共 Provider。

    返回新创建的 Provider 实体。
    """
    submission = get_submission(session, submission_id)
    if submission is None:
        raise ProviderSubmissionNotFoundError(f"Submission {submission_id} not found")

    provider = Provider(
        provider_id=submission.provider_id,
        name=submission.name,
        base_url=submission.base_url,
        transport="http",
        provider_type=submission.provider_type or "native",
        weight=1.0,
        visibility="public",
    )
    session.add(provider)
    session.flush()  # ensure provider.id

    if submission.encrypted_api_key:
        api_key = ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=submission.encrypted_api_key,
            weight=1.0,
            max_qps=None,
            label="default",
            status="active",
        )
        session.add(api_key)

    # 关键：保存 Provider 关联到 Submission，用于后续取消时删除
    submission.approved_provider_uuid = provider.id
    submission.approval_status = "approved"
    submission.reviewed_by = reviewer_id
    submission.review_notes = review_notes
    submission.reviewed_at = datetime.now(timezone.utc)

    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover
        session.rollback()
        logger.error("Failed to approve provider submission: %s", exc)
        raise ProviderSubmissionServiceError("无法通过提供商提交") from exc

    session.refresh(provider)

    # 通知提交者审核通过
    try:
        create_notification(
            session,
            NotificationCreateRequest(
                title="共享提供商审核通过",
                content=(
                    f"提交 {submission.name} 已通过审核。"
                    f"{' 审核备注: ' + review_notes if review_notes else ''}"
                ),
                level="success",
                target_type="users",
                target_user_ids=[submission.user_id],
            ),
            creator_id=reviewer_id,
        )
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to send approval notification for submission %s", submission_id
        )
    return provider


def reject_submission(
    session: Session,
    submission_id: UUID,
    reviewer_id: UUID,
    review_notes: str | None = None,
) -> ProviderSubmission:
    """将提交标记为拒绝，不会创建 Provider。"""
    submission = get_submission(session, submission_id)
    if submission is None:
        raise ProviderSubmissionNotFoundError(f"Submission {submission_id} not found")

    submission.approval_status = "rejected"
    submission.reviewed_by = reviewer_id
    submission.review_notes = review_notes
    submission.reviewed_at = datetime.now(timezone.utc)

    session.add(submission)
    session.commit()
    session.refresh(submission)

    # 通知提交者审核拒绝
    try:
        create_notification(
            session,
            NotificationCreateRequest(
                title="共享提供商审核未通过",
                content=(
                    f"提交 {submission.name} 被拒绝。"
                    f"{' 原因: ' + review_notes if review_notes else ''}"
                ),
                level="warning",
                target_type="users",
                target_user_ids=[submission.user_id],
            ),
            creator_id=reviewer_id,
        )
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to send rejection notification for submission %s", submission_id
        )
    return submission


def cancel_submission(
    session: Session,
    submission_id: UUID,
    user_id: UUID,
) -> None:
    """用户取消自己的提交。
    
    根据提交状态执行不同的操作：
    - pending: 直接删除提交记录
    - approved: 删除对应的公共 Provider（级联删除相关数据）和提交记录
    - rejected: 直接删除提交记录
    
    Args:
        session: 数据库会话
        submission_id: 提交记录 ID
        user_id: 当前用户 ID（用于权限验证）
    
    Raises:
        ProviderSubmissionNotFoundError: 提交记录不存在
        ProviderSubmissionServiceError: 无权取消他人的提交
    """
    submission = get_submission(session, submission_id)
    if submission is None:
        raise ProviderSubmissionNotFoundError(f"Submission {submission_id} not found")
    
    # 验证权限：只能取消自己的提交
    if submission.user_id != user_id:
        raise ProviderSubmissionServiceError("无权取消他人的提交")
    
    # 根据状态执行不同的删除逻辑
    if submission.approval_status == "approved":
        # 已批准：需要删除对应的公共 Provider
        if submission.approved_provider_uuid:
            provider = session.get(Provider, submission.approved_provider_uuid)
            if provider:
                logger.info(
                    "Deleting approved provider %s (id=%s) due to submission cancellation",
                    provider.provider_id,
                    provider.id,
                )
                session.delete(provider)  # 级联删除 API Keys、Models 等
        else:
            # 理论上不应该出现这种情况，但为了健壮性记录警告
            logger.warning(
                "Approved submission %s has no approved_provider_uuid",
                submission_id,
            )
    
    # 删除提交记录（pending、approved、rejected 都删除）
    session.delete(submission)
    
    try:
        session.commit()
        logger.info(
            "Submission %s (status=%s) cancelled by user %s",
            submission_id,
            submission.approval_status,
            user_id,
        )
    except IntegrityError as exc:  # pragma: no cover
        session.rollback()
        logger.error("Failed to cancel submission: %s", exc)
        raise ProviderSubmissionServiceError("无法取消提交") from exc


__all__ = [
    "ProviderSubmissionServiceError",
    "ProviderSubmissionNotFoundError",
    "approve_submission",
    "cancel_submission",
    "create_submission",
    "get_submission",
    "list_submissions",
    "list_user_submissions",
    "reject_submission",
]
