from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_http_client, get_redis
from app.errors import bad_request, forbidden, not_found
from app.http_client import CurlCffiClient
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.model_cache import MODELS_CACHE_KEY
from app.schemas import (
    ProviderSharedUsersResponse,
    ProviderSharedUsersUpdateRequest,
    ProviderSubmissionRequest,
    ProviderSubmissionResponse,
    UserProbeRunResponse,
    UserProbeTaskCreateRequest,
    UserProbeTaskResponse,
    UserProbeTaskUpdateRequest,
    UserProviderCreateRequest,
    UserProviderResponse,
    UserProviderUpdateRequest,
    UserQuotaResponse,
)
from app.services.encryption import decrypt_secret
from app.services.provider_submission_service import (
    ProviderSubmissionServiceError,
    create_submission,
)
from app.services.provider_validation_service import ProviderValidationService
from app.services.user_permission_service import UserPermissionService
from app.services.user_probe_service import (
    UserProbeConflictError,
    UserProbeNotFoundError,
    UserProbeServiceError,
    create_user_probe_task,
    delete_user_probe_task,
    get_user_probe_task,
    list_user_probe_runs,
    list_user_probe_tasks,
    run_user_probe_task_once,
    update_user_probe_task,
)
from app.services.user_provider_service import (
    UserProviderNotFoundError,
    UserProviderServiceError,
    count_user_private_providers,
    create_private_provider,
    get_private_provider_by_id,
    list_private_providers,
    update_private_provider,
    update_provider_shared_users,
)
from app.settings import settings
from app.storage.redis_service import PROVIDER_MODELS_KEY_TEMPLATE

router = APIRouter(
    tags=["user-providers"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_can_manage_user(current: AuthenticatedUser, target_user_id: UUID) -> None:
    if current.is_superuser:
        return
    if current.id != str(target_user_id):
        raise forbidden("无权管理其他用户的私有提供商")


async def _invalidate_provider_model_caches(redis: Redis, provider_id: str) -> None:
    """
    清理与 provider 模型列表相关的缓存：
    - `gateway:models:all`：全局 /models 聚合缓存（MODELS_CACHE_KEY）
    - `llm:vendor:{provider_id}:models`：单 provider 的模型列表缓存

    注意：逻辑模型缓存（`llm:logical:*`）由 invalidate_logical_models_cache 负责。
    """
    if redis is object:
        return
    keys = [
        MODELS_CACHE_KEY,
        PROVIDER_MODELS_KEY_TEMPLATE.format(provider_id=provider_id),
    ]
    try:
        await redis.delete(*keys)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - 缓存清理失败不阻断主流程
        logger.warning(
            "Failed to invalidate provider model caches for %s", provider_id, exc_info=True
        )


def _run_to_response(run, *, provider_id: str) -> UserProbeRunResponse:
    return UserProbeRunResponse(
        id=run.id,
        task_id=run.task_uuid,
        user_id=run.user_id,
        provider_id=provider_id,
        model_id=run.model_id,
        api_style=run.api_style,
        success=run.success,
        status_code=run.status_code,
        latency_ms=run.latency_ms,
        error_message=run.error_message,
        response_text=run.response_text,
        response_excerpt=run.response_excerpt,
        response_json=run.response_json,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _task_to_response(task, *, provider_id: str) -> UserProbeTaskResponse:
    last_run = getattr(task, "last_run", None)
    return UserProbeTaskResponse(
        id=task.id,
        user_id=task.user_id,
        provider_id=provider_id,
        name=task.name,
        model_id=task.model_id,
        prompt=task.prompt,
        interval_seconds=task.interval_seconds,
        max_tokens=task.max_tokens,
        api_style=task.api_style,
        enabled=task.enabled,
        in_progress=task.in_progress,
        last_run_at=task.last_run_at,
        next_run_at=task.next_run_at,
        last_run=_run_to_response(last_run, provider_id=provider_id) if last_run else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get(
    "/users/{user_id}/quota",
    response_model=UserQuotaResponse,
)
def get_user_quota_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserQuotaResponse:
    """
    获取指定用户的私有 Provider 配额信息。

    - 仅支持本人或超级管理员查询；
    - `private_provider_limit` 为展示用上限值；
    - 对于超级管理员或拥有 `unlimited_providers` 权限的用户，会返回 `is_unlimited=True`，
      此时 `private_provider_limit` 仅作为前端展示建议值，后端不会做硬性限制。
    """

    _ensure_can_manage_user(current_user, user_id)

    perm = UserPermissionService(db)
    raw_limit = perm.get_provider_limit(user_id)
    is_unlimited = raw_limit is None
    # 对于无限制用户，给出一个合理的展示上限，避免前端进度条失真
    display_limit = (
        settings.max_user_private_provider_limit
        if is_unlimited
        else int(raw_limit)
    )

    current_count = count_user_private_providers(db, user_id)

    return UserQuotaResponse(
        private_provider_limit=display_limit,
        private_provider_count=current_count,
        is_unlimited=is_unlimited,
    )


@router.post(
    "/users/{user_id}/private-providers",
    response_model=UserProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_private_provider_endpoint(
    user_id: UUID,
    payload: UserProviderCreateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProviderResponse:
    """为指定用户创建一个私有提供商，仅该用户的 API Key 可选择使用。"""

    _ensure_can_manage_user(current_user, user_id)

    perm = UserPermissionService(db)
    if not perm.has_permission(user_id, "create_private_provider"):
        raise forbidden("当前用户未被授予创建私有提供商的权限")

    limit = perm.get_provider_limit(user_id)
    if limit is not None:
        current_count = count_user_private_providers(db, user_id)
        if current_count >= limit:
            raise forbidden(f"已达到私有提供商数量限制（{limit}）")

    try:
        provider = create_private_provider(db, user_id, payload)
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))

    # 失效逻辑模型缓存，下次查询时会从数据库回源
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys after creating provider %s", deleted, provider.provider_id)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")

    # 同步失效模型列表缓存，避免 /providers/{id}/models 与 /v1/models 返回旧数据。
    await _invalidate_provider_model_caches(redis, provider.provider_id)

    return UserProviderResponse.model_validate(provider)


@router.get(
    "/users/{user_id}/private-providers",
    response_model=list[UserProviderResponse],
)
def list_private_providers_endpoint(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[UserProviderResponse]:
    """获取用户的私有提供商列表。"""

    _ensure_can_manage_user(current_user, user_id)
    providers = list_private_providers(db, user_id)
    return [UserProviderResponse.model_validate(p) for p in providers]


@router.put(
    "/users/{user_id}/private-providers/{provider_id}",
    response_model=UserProviderResponse,
)
async def update_private_provider_endpoint(
    user_id: UUID,
    provider_id: str,
    payload: UserProviderUpdateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProviderResponse:
    """更新用户的私有提供商配置。"""

    _ensure_can_manage_user(current_user, user_id)

    try:
        provider = update_private_provider(db, user_id, provider_id, payload)
    except UserProviderNotFoundError:
        raise not_found(f"Private provider '{provider_id}' not found")
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))

    # 失效逻辑模型缓存，下次查询时会从数据库回源
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys after updating provider %s", deleted, provider_id)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")

    # 失效模型列表缓存，确保 provider 模型配置更新后能尽快生效。
    await _invalidate_provider_model_caches(redis, provider_id)

    return UserProviderResponse.model_validate(provider)


@router.get(
    "/users/{user_id}/private-providers/{provider_id}/shared-users",
    response_model=ProviderSharedUsersResponse,
)
def list_provider_shared_users_endpoint(
    user_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSharedUsersResponse:
    """查询私有 Provider 的授权用户列表。"""

    _ensure_can_manage_user(current_user, user_id)

    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"Private provider '{provider_id}' not found")

    shared_ids = [link.user_id for link in provider.shared_users]
    return ProviderSharedUsersResponse(
        provider_id=provider.provider_id,
        visibility=provider.visibility,
        shared_user_ids=shared_ids,
    )


@router.put(
    "/users/{user_id}/private-providers/{provider_id}/shared-users",
    response_model=ProviderSharedUsersResponse,
)
def update_provider_shared_users_endpoint(
    user_id: UUID,
    provider_id: str,
    payload: ProviderSharedUsersUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSharedUsersResponse:
    """设置或清空私有 Provider 的授权用户列表。"""

    _ensure_can_manage_user(current_user, user_id)

    try:
        provider = update_provider_shared_users(
            db, user_id, provider_id, payload.user_ids
        )
    except UserProviderNotFoundError:
        raise not_found(f"Private provider '{provider_id}' not found")
    except UserProviderServiceError as exc:
        raise bad_request(str(exc))

    shared_ids = [link.user_id for link in provider.shared_users]
    return ProviderSharedUsersResponse(
        provider_id=provider.provider_id,
        visibility=provider.visibility,
        shared_user_ids=shared_ids,
    )


@router.post(
    "/users/{user_id}/private-providers/{provider_id}/submit-shared",
    response_model=ProviderSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_private_provider_to_shared_pool_endpoint(
    user_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderSubmissionResponse:
    """
    将用户的私有 Provider 一键提交到共享池，进入管理员审核流程。

    - 仅允许本人或超级管理员操作；
    - 需要具备 `submit_shared_provider` 权限；
    - 会从对应私有 Provider 上选择一条启用中的上游 API 密钥进行验证；
    - 验证通过后创建一条 ProviderSubmission 记录，状态为 pending。
    """

    # 只能操作自己的私有 Provider
    _ensure_can_manage_user(current_user, user_id)

    perm = UserPermissionService(db)
    if not perm.has_permission(user_id, "submit_shared_provider"):
        raise forbidden("当前用户未被授予提交共享提供商的权限")

    # 查找对应的私有 Provider（确保 owner_id/visibility 匹配）
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    # 从 Provider 的上游密钥中挑选一条启用中的密钥
    active_key = next(
        (k for k in provider.api_keys if getattr(k, "status", "") == "active"),
        None,
    )
    if active_key is None:
        raise bad_request("当前私有提供商未配置可用的上游 API 密钥")

    # 解密上游 API Key
    try:
        api_key_plain = decrypt_secret(active_key.encrypted_key)
    except ValueError:
        raise bad_request("无法解密上游 API 密钥，请联系管理员")

    # 复用 ProviderValidationService 做连通性验证
    validator = ProviderValidationService()
    validation = await validator.validate_provider_config(
        provider.base_url,
        api_key_plain,
        provider.provider_type,
    )
    if not validation.is_valid:
        raise bad_request(f"提供商配置验证失败: {validation.error_message or '未知错误'}")

    # 构造提交请求 payload，并创建提交记录
    payload = ProviderSubmissionRequest(
        name=provider.name,
        provider_id=provider.provider_id,
        base_url=provider.base_url,
        provider_type=provider.provider_type or "native",
        api_key=api_key_plain,
    )

    try:
        submission = create_submission(
            db,
            user_id,
            payload,
            metadata=validation.metadata,
        )
    except ProviderSubmissionServiceError as exc:
        raise bad_request(str(exc))

    return ProviderSubmissionResponse.model_validate(submission)


@router.get(
    "/users/{user_id}/private-providers/{provider_id}/probe-tasks",
    response_model=list[UserProbeTaskResponse],
)
def list_user_probe_tasks_endpoint(
    user_id: UUID,
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[UserProbeTaskResponse]:
    """列出当前用户在该私有 Provider 下创建的探针任务。"""
    _ensure_can_manage_user(current_user, user_id)
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    tasks = list_user_probe_tasks(db, user_id=user_id, provider=provider)
    return [_task_to_response(t, provider_id=provider_id) for t in tasks]


@router.post(
    "/users/{user_id}/private-providers/{provider_id}/probe-tasks",
    response_model=UserProbeTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_probe_task_endpoint(
    user_id: UUID,
    provider_id: str,
    payload: UserProbeTaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProbeTaskResponse:
    """为指定私有 Provider 创建一个用户探针任务。"""
    _ensure_can_manage_user(current_user, user_id)
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    try:
        task = create_user_probe_task(
            db,
            user_id=user_id,
            provider=provider,
            name=payload.name,
            model_id=payload.model_id,
            prompt=payload.prompt,
            interval_seconds=payload.interval_seconds,
            max_tokens=payload.max_tokens,
            api_style=payload.api_style,
            enabled=payload.enabled,
        )
    except UserProbeServiceError as exc:
        raise bad_request(str(exc))

    return _task_to_response(task, provider_id=provider_id)


@router.put(
    "/users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}",
    response_model=UserProbeTaskResponse,
)
def update_user_probe_task_endpoint(
    user_id: UUID,
    provider_id: str,
    task_id: UUID,
    payload: UserProbeTaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProbeTaskResponse:
    """更新一个用户探针任务的配置（启用/频率/模型/prompt 等）。"""
    _ensure_can_manage_user(current_user, user_id)
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    try:
        task = get_user_probe_task(db, user_id=user_id, provider=provider, task_id=task_id)
        task = update_user_probe_task(
            db,
            task=task,
            name=payload.name,
            model_id=payload.model_id,
            prompt=payload.prompt,
            interval_seconds=payload.interval_seconds,
            max_tokens=payload.max_tokens,
            api_style=payload.api_style,
            enabled=payload.enabled,
        )
    except UserProbeNotFoundError:
        raise not_found("探针任务不存在")
    except UserProbeConflictError as exc:
        raise bad_request(str(exc))
    except UserProbeServiceError as exc:
        raise bad_request(str(exc))

    return _task_to_response(task, provider_id=provider_id)


@router.delete(
    "/users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user_probe_task_endpoint(
    user_id: UUID,
    provider_id: str,
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> None:
    """删除一个用户探针任务。"""
    _ensure_can_manage_user(current_user, user_id)
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    try:
        task = get_user_probe_task(db, user_id=user_id, provider=provider, task_id=task_id)
        delete_user_probe_task(db, task=task)
    except UserProbeNotFoundError:
        raise not_found("探针任务不存在")
    except UserProbeConflictError as exc:
        raise bad_request(str(exc))


@router.post(
    "/users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}/run",
    response_model=UserProbeRunResponse,
)
async def run_user_probe_task_now_endpoint(
    user_id: UUID,
    provider_id: str,
    task_id: UUID,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    http_client: CurlCffiClient = Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProbeRunResponse:
    """立即执行一次探针任务，并返回本次对话探针结果。"""
    _ensure_can_manage_user(current_user, user_id)
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    try:
        task = get_user_probe_task(db, user_id=user_id, provider=provider, task_id=task_id)
    except UserProbeNotFoundError:
        raise not_found("探针任务不存在")

    # 测试环境经常会用简化版 Redis stub（缺少 zset API），此时退回 None 即可。
    effective_redis = None if redis is object or not hasattr(redis, "zadd") else redis
    try:
        run = await run_user_probe_task_once(
            db,
            task=task,
            provider=provider,
            client=http_client,
            redis=effective_redis,
            allow_disabled=True,
        )
    except UserProbeConflictError as exc:
        raise bad_request(str(exc))
    except UserProbeServiceError as exc:
        raise bad_request(str(exc))

    return _run_to_response(run, provider_id=provider_id)


@router.get(
    "/users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}/runs",
    response_model=list[UserProbeRunResponse],
)
def list_user_probe_runs_endpoint(
    user_id: UUID,
    provider_id: str,
    task_id: UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[UserProbeRunResponse]:
    """查看某个探针任务的近期执行记录。"""
    _ensure_can_manage_user(current_user, user_id)
    provider = get_private_provider_by_id(db, user_id, provider_id)
    if provider is None:
        raise not_found(f"私有提供商 '{provider_id}' 不存在")

    try:
        task = get_user_probe_task(db, user_id=user_id, provider=provider, task_id=task_id)
        runs = list_user_probe_runs(db, task=task, limit=limit)
    except UserProbeNotFoundError:
        raise not_found("探针任务不存在")

    return [_run_to_response(r, provider_id=provider_id) for r in runs]


__all__ = ["router"]
