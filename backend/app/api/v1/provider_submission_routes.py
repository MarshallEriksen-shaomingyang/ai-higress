from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas import (
    ProviderReviewRequest,
    ProviderSubmissionRequest,
    ProviderSubmissionResponse,
)
from app.services.provider_submission_service import (
    ProviderSubmissionNotFoundError,
    ProviderSubmissionServiceError,
    approve_submission,
    create_submission,
    get_submission,
    list_submissions,
    reject_submission,
)
from app.services.provider_validation_service import ProviderValidationService
from app.services.user_permission_service import UserPermissionService

router = APIRouter(
    tags=["provider-submissions"],
    dependencies=[Depends(require_jwt_token)],
)


@router.post(
    "/providers/submissions",
    response_model=ProviderSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_provider_endpoint(
    payload: ProviderSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSubmissionResponse:
    """用户提交新的共享提供商，将进入管理员审核流程。"""

    perm = UserPermissionService(db)
    if not perm.has_permission(UUID(current_user.id), "submit_shared_provider"):
        raise forbidden("当前用户未被授权提交共享提供商")

    validator = ProviderValidationService()
    validation = await validator.validate_provider_config(
        str(payload.base_url),
        payload.api_key,
        payload.provider_type,
    )
    if not validation.is_valid:
        raise bad_request(f"提供商配置验证失败: {validation.error_message or '未知错误'}")

    try:
        submission = create_submission(
            db,
            UUID(current_user.id),
            payload,
            metadata=validation.metadata,
        )
    except ProviderSubmissionServiceError as exc:
        raise bad_request(str(exc))

    return ProviderSubmissionResponse.model_validate(submission)


@router.get(
    "/providers/submissions",
    response_model=list[ProviderSubmissionResponse],
)
def list_provider_submissions_endpoint(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="按审批状态过滤：pending/approved/rejected",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderSubmissionResponse]:
    """管理员查看所有提供商提交记录。"""

    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")

    submissions = list_submissions(db, status_filter)
    return [ProviderSubmissionResponse.model_validate(s) for s in submissions]


@router.put(
    "/providers/submissions/{submission_id}/review",
    response_model=ProviderSubmissionResponse,
)
def review_provider_submission_endpoint(
    submission_id: UUID,
    payload: ProviderReviewRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSubmissionResponse:
    """管理员审核共享提供商提交。"""

    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")

    try:
        # 确保提交存在
        submission = get_submission(db, submission_id)
        if submission is None:
            raise not_found("提交记录不存在")

        if payload.approved:
            approve_submission(
                db,
                submission_id,
                UUID(current_user.id),
                payload.review_notes,
            )
        else:
            reject_submission(
                db,
                submission_id,
                UUID(current_user.id),
                payload.review_notes,
            )
        # 重新读取最新提交状态
        submission = get_submission(db, submission_id)
        if submission is None:
            raise not_found("提交记录不存在")
        return ProviderSubmissionResponse.model_validate(submission)
    except ProviderSubmissionNotFoundError:
        raise not_found("提交记录不存在")
    except ProviderSubmissionServiceError as exc:
        raise bad_request(str(exc))


__all__ = ["router"]

