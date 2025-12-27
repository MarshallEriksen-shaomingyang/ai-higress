from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Provider, ProviderAPIKey, ProviderSubmission


class ProviderIdConflictError(RuntimeError):
    """provider_id 冲突：已存在且不可复用。"""


def get_submission(db: Session, *, submission_id: UUID) -> ProviderSubmission | None:
    try:
        return db.get(ProviderSubmission, submission_id)
    except Exception:
        return None


def list_submissions(db: Session, *, status: str | None = None) -> list[ProviderSubmission]:
    stmt: Select[tuple[ProviderSubmission]] = select(ProviderSubmission).order_by(
        ProviderSubmission.created_at.desc()
    )
    if status:
        stmt = stmt.where(ProviderSubmission.approval_status == status)
    return list(db.execute(stmt).scalars().all())


def list_user_submissions(
    db: Session,
    *,
    user_id: UUID,
    status: str | None = None,
) -> list[ProviderSubmission]:
    stmt: Select[tuple[ProviderSubmission]] = (
        select(ProviderSubmission)
        .where(ProviderSubmission.user_id == user_id)
        .order_by(ProviderSubmission.created_at.desc())
    )
    if status:
        stmt = stmt.where(ProviderSubmission.approval_status == status)
    return list(db.execute(stmt).scalars().all())


def create_submission(db: Session, *, submission: ProviderSubmission) -> ProviderSubmission:
    db.add(submission)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(submission)
    return submission


def approve_submission(
    db: Session,
    *,
    submission: ProviderSubmission,
    reviewer_id: UUID,
    status: str,
    reviewed_at: datetime,
    review_notes: str | None,
    limit_qps: int | None,
) -> tuple[Provider, bool]:
    """
    审核通过一个提交并创建/复用对应的公共 Provider。

    返回 (provider, reused_private_provider)。
    """
    provider: Provider | None = None
    reused_private_provider = False

    existing_provider = (
        db.execute(select(Provider).where(Provider.provider_id == submission.provider_id))
        .scalars()
        .first()
    )
    if existing_provider is not None:
        is_user_private_provider = (
            existing_provider.owner_id == submission.user_id
            and existing_provider.visibility in ("private", "restricted")
        )
        if is_user_private_provider:
            provider = existing_provider
            reused_private_provider = True
        else:
            raise ProviderIdConflictError(f"provider_id '{submission.provider_id}' 已存在")

    if provider is None:
        provider = Provider(
            provider_id=submission.provider_id,
            name=submission.name,
            base_url=submission.base_url,
            transport="http",
            provider_type=submission.provider_type or "native",
            weight=1.0,
            visibility="public",
            audit_status=status or "approved",
            operation_status="active",
            max_qps=limit_qps,
        )
        db.add(provider)
        db.flush()  # ensure provider.id

        if submission.encrypted_api_key:
            api_key = ProviderAPIKey(
                provider_uuid=provider.id,
                encrypted_key=submission.encrypted_api_key,
                weight=1.0,
                max_qps=None,
                label="default",
                status="active",
            )
            db.add(api_key)
    else:
        provider.name = submission.name
        provider.base_url = submission.base_url
        provider.provider_type = submission.provider_type or provider.provider_type
        provider.visibility = "public"
        provider.owner_id = None
        provider.audit_status = status or "approved"
        provider.operation_status = "active"
        provider.max_qps = limit_qps
        provider.weight = provider.weight or 1.0
        provider.transport = provider.transport or "http"
        reused_private_provider = True

    submission.approved_provider_uuid = provider.id
    submission.approval_status = status or "approved"
    submission.reviewed_by = reviewer_id
    submission.review_notes = review_notes
    submission.reviewed_at = reviewed_at

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    if not reused_private_provider:
        db.refresh(provider)
    return provider, reused_private_provider


def reject_submission(
    db: Session,
    *,
    submission: ProviderSubmission,
    reviewer_id: UUID,
    reviewed_at: datetime,
    review_notes: str | None,
) -> ProviderSubmission:
    submission.approval_status = "rejected"
    submission.reviewed_by = reviewer_id
    submission.review_notes = review_notes
    submission.reviewed_at = reviewed_at
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def cancel_submission(
    db: Session,
    *,
    submission: ProviderSubmission,
    delete_provider: Provider | None,
) -> None:
    if delete_provider is not None:
        db.delete(delete_provider)
    db.delete(submission)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


__all__ = [
    "ProviderIdConflictError",
    "approve_submission",
    "cancel_submission",
    "create_submission",
    "get_submission",
    "list_submissions",
    "list_user_submissions",
    "reject_submission",
]
