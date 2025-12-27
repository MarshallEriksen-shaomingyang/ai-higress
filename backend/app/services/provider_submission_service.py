from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Provider, ProviderAPIKey, ProviderSubmission
from app.repositories.provider_repository import get_provider_by_provider_id, get_provider_by_uuid
from app.repositories.provider_submission_repository import (
    ProviderIdConflictError,
    approve_submission as repo_approve_submission,
    cancel_submission as repo_cancel_submission,
    create_submission as repo_create_submission,
    get_submission as repo_get_submission,
    list_submissions as repo_list_submissions,
    list_user_submissions as repo_list_user_submissions,
    reject_submission as repo_reject_submission,
)
from app.schemas.notification import NotificationCreateRequest
from app.schemas.provider_control import (
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

    # 提交前先校验 provider_id 是否已被占用，允许当前用户的私有 Provider 复用该 ID。
    existing_provider = get_provider_by_provider_id(session, provider_id=payload.provider_id)
    if existing_provider is not None:
        is_user_private_provider = (
            existing_provider.owner_id == user_id
            and existing_provider.visibility in ("private", "restricted")
        )
        if not is_user_private_provider:
            raise ProviderSubmissionServiceError(
                f"provider_id '{payload.provider_id}' 已存在，请更换后再提交"
            )

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

    try:
        submission = repo_create_submission(session, submission=submission)
    except IntegrityError as exc:  # pragma: no cover - 并发保护
        logger.error("Failed to create provider submission: %s", exc)
        raise ProviderSubmissionServiceError("无法创建提供商提交记录") from exc

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
    status: str | None = None,
) -> list[ProviderSubmission]:
    """按可选状态过滤列出提交记录。"""
    return repo_list_submissions(session, status=status)


def list_user_submissions(
    session: Session,
    user_id: UUID,
    status: str | None = None,
) -> list[ProviderSubmission]:
    """按用户和可选状态过滤列出提交记录。"""
    return repo_list_user_submissions(session, user_id=user_id, status=status)


def get_submission(session: Session, submission_id: UUID) -> ProviderSubmission | None:
    return repo_get_submission(session, submission_id=submission_id)


def approve_submission(
    session: Session,
    submission_id: UUID,
    reviewer_id: UUID,
    review_notes: str | None = None,
    status: str = "approved",
    limit_qps: int | None = None,
) -> Provider:
    """审核通过一个提交并创建对应的公共 Provider。

    返回新创建的 Provider 实体。
    """
    submission = repo_get_submission(session, submission_id=submission_id)
    if submission is None:
        raise ProviderSubmissionNotFoundError(f"Submission {submission_id} not found")

    if submission.approval_status in ("approved", "approved_limited"):
        raise ProviderSubmissionServiceError("该提交已通过审核，无需重复审批")
    if submission.approval_status == "rejected":
        raise ProviderSubmissionServiceError("该提交已被拒绝，无法再次审批")

    try:
        provider, reused_private_provider = repo_approve_submission(
            session,
            submission=submission,
            reviewer_id=reviewer_id,
            status=status,
            reviewed_at=datetime.now(UTC),
            review_notes=review_notes,
            limit_qps=limit_qps,
        )
    except IntegrityError as exc:  # pragma: no cover
        logger.error("Failed to approve provider submission: %s", exc)
        raise ProviderSubmissionServiceError("无法通过提供商提交") from exc
    except ProviderIdConflictError as exc:
        raise ProviderSubmissionServiceError(str(exc)) from exc

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

    # 广播公共池新增通知
    try:
        create_notification(
            session,
            NotificationCreateRequest(
                title="公共池新增提供商",
                content=(
                    f"共享提供商 {submission.name}（ID: {submission.provider_id}）已通过审核，"
                    "现已加入公共池供所有用户使用。"
                ),
                level="success",
                target_type="all",
            ),
            creator_id=reviewer_id,
        )
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to broadcast approval notification for submission %s", submission_id
        )
    return provider


def reject_submission(
    session: Session,
    submission_id: UUID,
    reviewer_id: UUID,
    review_notes: str | None = None,
) -> ProviderSubmission:
    """将提交标记为拒绝，不会创建 Provider。"""
    submission = repo_get_submission(session, submission_id=submission_id)
    if submission is None:
        raise ProviderSubmissionNotFoundError(f"Submission {submission_id} not found")
    submission = repo_reject_submission(
        session,
        submission=submission,
        reviewer_id=reviewer_id,
        reviewed_at=datetime.now(UTC),
        review_notes=review_notes,
    )

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
    submission = repo_get_submission(session, submission_id=submission_id)
    if submission is None:
        raise ProviderSubmissionNotFoundError(f"Submission {submission_id} not found")

    # 验证权限：只能取消自己的提交
    if submission.user_id != user_id:
        raise ProviderSubmissionServiceError("无权取消他人的提交")

    delete_provider = None
    if submission.approval_status == "approved" and submission.approved_provider_uuid:
        delete_provider = get_provider_by_uuid(session, provider_uuid=submission.approved_provider_uuid)

    try:
        repo_cancel_submission(session, submission=submission, delete_provider=delete_provider)
        logger.info(
            "Submission %s (status=%s) cancelled by user %s",
            submission_id,
            submission.approval_status,
            user_id,
        )
    except IntegrityError as exc:  # pragma: no cover
        logger.error("Failed to cancel submission: %s", exc)
        raise ProviderSubmissionServiceError("无法取消提交") from exc


__all__ = [
    "ProviderSubmissionNotFoundError",
    "ProviderSubmissionServiceError",
    "approve_submission",
    "cancel_submission",
    "create_submission",
    "get_submission",
    "list_submissions",
    "list_user_submissions",
    "reject_submission",
]
