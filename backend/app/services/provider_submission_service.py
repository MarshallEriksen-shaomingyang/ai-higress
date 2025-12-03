from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Provider, ProviderAPIKey, ProviderSubmission
from app.schemas.provider_control import (
    ProviderReviewRequest,
    ProviderSubmissionRequest,
)
from app.services.encryption import encrypt_secret


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
    return submission


def list_submissions(session: Session, status: Optional[str] = None) -> List[ProviderSubmission]:
    """按可选状态过滤列出提交记录。"""
    stmt: Select[tuple[ProviderSubmission]] = select(ProviderSubmission).order_by(
        ProviderSubmission.created_at.desc()
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

    submission.approval_status = "approved"
    submission.reviewed_by = reviewer_id
    submission.review_notes = review_notes
    submission.reviewed_at = datetime.now(timezone.utc)

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

    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover
        session.rollback()
        logger.error("Failed to approve provider submission: %s", exc)
        raise ProviderSubmissionServiceError("无法通过提供商提交") from exc

    session.refresh(provider)
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
    return submission


__all__ = [
    "ProviderSubmissionServiceError",
    "ProviderSubmissionNotFoundError",
    "approve_submission",
    "create_submission",
    "get_submission",
    "list_submissions",
    "reject_submission",
]

