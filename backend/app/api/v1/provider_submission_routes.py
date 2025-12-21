from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.model_cache import MODELS_CACHE_KEY
from app.schemas import (
    ProviderReviewRequest,
    ProviderSubmissionRequest,
    ProviderSubmissionResponse,
)
from app.services.provider_submission_service import (
    ProviderSubmissionNotFoundError,
    ProviderSubmissionServiceError,
    approve_submission,
    cancel_submission,
    create_submission,
    get_submission,
    list_submissions,
    list_user_submissions,
    reject_submission,
)
from app.services.provider_validation_service import ProviderValidationService
from app.services.user_permission_service import UserPermissionService
from app.storage.redis_service import PROVIDER_MODELS_KEY_TEMPLATE

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


@router.get(
    "/providers/submissions/me",
    response_model=list[ProviderSubmissionResponse],
)
def list_my_provider_submissions_endpoint(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="按审批状态过滤：pending/approved/rejected",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderSubmissionResponse]:
    """当前用户查看自己的共享提供商提交记录。"""

    submissions = list_user_submissions(db, UUID(current_user.id), status_filter)
    return [ProviderSubmissionResponse.model_validate(s) for s in submissions]


async def _invalidate_public_provider_cache(redis: Redis, provider_id: str) -> None:
    """
    清理公共池相关缓存，确保审核通过的 Provider 能即时出现在 /models 等接口中。
    """
    if redis is object:
        return
    keys = [
        MODELS_CACHE_KEY,
        PROVIDER_MODELS_KEY_TEMPLATE.format(provider_id=provider_id),
    ]
    try:
        await redis.delete(*keys)
    except Exception:  # pragma: no cover - 缓存清理失败不阻断主流程
        logger.warning(
            "Failed to invalidate provider cache for %s", provider_id, exc_info=True
        )

@router.put(
    "/providers/submissions/{submission_id}/review",
    response_model=ProviderSubmissionResponse,
)
async def review_provider_submission_endpoint(
    submission_id: UUID,
    payload: ProviderReviewRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    redis: Redis = Depends(get_redis),
) -> ProviderSubmissionResponse:
    """管理员审核共享提供商提交。"""

    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")

    try:
        # 确保提交存在
        submission = get_submission(db, submission_id)
        if submission is None:
            raise not_found("提交记录不存在")

        decision = payload.decision
        if decision is None:
            decision = "approved" if payload.approved else "rejected"

        if decision not in ("approved", "approved_limited", "rejected"):
            raise bad_request("不支持的审核决策")

        if decision == "rejected" and not payload.review_notes:
            raise bad_request("拒绝时请填写审核备注")

        if decision.startswith("approved"):
            approve_submission(
                db,
                submission_id,
                UUID(current_user.id),
                payload.review_notes,
                status=decision,
                limit_qps=payload.limit_qps,
            )
            await _invalidate_public_provider_cache(redis, submission.provider_id)
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


@router.delete(
    "/providers/submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_submission_endpoint(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    """用户取消自己的提交。
    
    根据提交状态执行不同的操作：
    - pending: 直接删除提交记录
    - approved: 删除对应的公共 Provider 和提交记录
    - rejected: 直接删除提交记录
    """

    try:
        cancel_submission(db, submission_id, UUID(current_user.id))
    except ProviderSubmissionNotFoundError:
        raise not_found("提交记录不存在")
    except ProviderSubmissionServiceError as exc:
        raise bad_request(str(exc))


__all__ = ["router"]
