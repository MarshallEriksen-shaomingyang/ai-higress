from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.models import Provider, ProviderModel
from app.provider.config import get_provider_config
from app.schemas import (
    AdminProviderResponse,
    AdminProvidersResponse,
    ModelPricingUpdateRequest,
    ProviderModelPricingResponse,
    ProviderAuditActionRequest,
    ProviderTestRequest,
    ProviderTestResult,
    ProviderAuditLogResponse,
    ProviderProbeConfigUpdate,
    ProviderModelValidationResult,
    ProviderVisibilityUpdateRequest,
)
from app.services.provider_audit_service import (
    ProviderAuditError,
    ProviderNotFoundError,
    approve_provider,
    get_latest_test_record,
    list_audit_logs,
    list_test_records,
    reject_provider,
    trigger_provider_test,
    update_operation_status,
    _get_provider,
)
from app.services.provider_validation_service import ProviderValidationService

router = APIRouter(
    tags=["admin-providers"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


def _to_test_result(provider: Provider, record) -> ProviderTestResult | None:
    if record is None:
        return None
    return ProviderTestResult(
        id=record.id,
        provider_id=provider.provider_id,
        mode=record.mode,
        success=record.success,
        summary=record.summary,
        probe_results=record.probe_results,
        latency_ms=record.latency_ms,
        error_code=record.error_code,
        cost=record.cost,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _build_admin_provider_response(
    db: Session,
    provider: Provider,
) -> AdminProviderResponse:
    latest_test = get_latest_test_record(db, provider.id)
    return AdminProviderResponse(
        id=provider.id,
        provider_id=provider.provider_id,
        name=provider.name,
        base_url=provider.base_url,
        provider_type=provider.provider_type,
        transport=provider.transport,
        sdk_vendor=provider.sdk_vendor,
        preset_id=provider.preset_id,
        visibility=provider.visibility,
        owner_id=provider.owner_id,
        status=provider.status,
        audit_status=provider.audit_status,
        operation_status=provider.operation_status,
        latest_test_result=_to_test_result(provider, latest_test),
        probe_enabled=provider.probe_enabled,
        probe_interval_seconds=provider.probe_interval_seconds,
        probe_model=provider.probe_model,
        last_check=provider.last_check,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _extract_static_model_ids(provider: Provider) -> list[str]:
    """从 Provider 的 static_models 或 models 关系中提取模型 ID 列表。"""
    model_ids: list[str] = []
    if provider.static_models:
        for item in provider.static_models:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item["id"]))
            elif isinstance(item, str):
                model_ids.append(item)
    if not model_ids and provider.models:
        model_ids = [m.model_id for m in provider.models if m.model_id]
    return model_ids


@router.get(
    "/admin/providers",
    response_model=AdminProvidersResponse,
)
def admin_list_providers_endpoint(
    visibility: str | None = Query(
        default=None,
        description="按可见性过滤：public/private/restricted",
    ),
    owner_id: UUID | None = Query(
        default=None,
        description="按所有者过滤（仅对 private 有意义）",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProvidersResponse:
    """管理员查看所有 Provider 列表。"""

    _ensure_admin(current_user)
    stmt: Select[tuple[Provider]] = select(Provider).order_by(Provider.created_at.desc())
    if visibility:
        stmt = stmt.where(Provider.visibility == visibility)
    if owner_id:
        stmt = stmt.where(Provider.owner_id == owner_id)
    providers = list(db.execute(stmt).scalars().all())
    return AdminProvidersResponse(
        providers=[_build_admin_provider_response(db, p) for p in providers],
        total=len(providers),
    )


@router.put(
    "/admin/providers/{provider_id}/visibility",
    response_model=AdminProviderResponse,
)
async def update_provider_visibility_endpoint(
    provider_id: str,
    payload: ProviderVisibilityUpdateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """更新 Provider 的可见性（public/private/restricted）。"""

    _ensure_admin(current_user)
    stmt: Select[tuple[Provider]] = select(Provider).where(
        Provider.provider_id == provider_id
    )
    provider = db.execute(stmt).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")

    provider.visibility = payload.visibility
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    # 失效逻辑模型缓存
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys after updating provider visibility %s", deleted, provider_id)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")
    
    return _build_admin_provider_response(db, provider)


@router.put(
    "/admin/providers/{provider_id}/probe-config",
    response_model=AdminProviderResponse,
)
async def update_provider_probe_config_endpoint(
    provider_id: str,
    payload: ProviderProbeConfigUpdate,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """更新 Provider 的探针配置（启用开关/自定义频率/指定模型）。"""

    _ensure_admin(current_user)
    stmt: Select[tuple[Provider]] = select(Provider).where(
        Provider.provider_id == provider_id
    )
    provider = db.execute(stmt).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")

    if payload.probe_enabled is not None:
        provider.probe_enabled = payload.probe_enabled
    if payload.probe_interval_seconds is not None:
        provider.probe_interval_seconds = payload.probe_interval_seconds
    if payload.probe_model is not None:
        provider.probe_model = payload.probe_model

    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    # 失效逻辑模型缓存
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys after updating provider probe config %s", deleted, provider_id)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")
    
    return _build_admin_provider_response(db, provider)


@router.post(
    "/admin/providers/{provider_id}/test",
    response_model=ProviderTestResult,
)
def admin_test_provider_endpoint(
    provider_id: str,
    payload: ProviderTestRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderTestResult:
    """管理员触发一次 Provider 探针测试。"""

    _ensure_admin(current_user)
    request = payload or ProviderTestRequest()
    try:
        record = trigger_provider_test(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            mode=request.mode,
            remark=request.remark,
            custom_input=request.input_text,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")

    provider = db.execute(
        select(Provider).where(Provider.provider_id == provider_id)
    ).scalars().first()
    if provider is None:
        # 理论上不应发生（trigger_provider_test 已校验），保护性返回 404
        raise not_found(f"Provider '{provider_id}' not found")
    return _to_test_result(provider, record)


@router.post(
    "/admin/providers/{provider_id}/validate-models",
    response_model=list[ProviderModelValidationResult],
)
async def validate_provider_models_endpoint(
    provider_id: str,
    limit: int = Query(
        default=1,
        ge=1,
        le=5,
        description="抽样验证的模型数量，默认 1，最多 5",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderModelValidationResult]:
    """对静态模型执行一次极小的对话调用，验证模型是否可用。"""

    _ensure_admin(current_user)
    provider = db.execute(
        select(Provider).where(Provider.provider_id == provider_id)
    ).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")

    cfg = get_provider_config(provider_id)
    if cfg is None:
        raise bad_request("未找到可用的 Provider 配置（缺少 API Key 或配置不完整）")
    api_keys = cfg.get_api_keys()
    if not api_keys:
        raise bad_request("未配置 API Key，无法验证模型")

    model_ids = _extract_static_model_ids(provider)
    if not model_ids:
        raise bad_request("未找到可验证的静态模型")

    validator = ProviderValidationService()
    results = await validator.validate_models_via_chat(
        str(cfg.base_url),
        api_keys[0].key,
        model_ids,
        path=cfg.chat_completions_path or cfg.messages_path or "/v1/chat/completions",
        sample_size=limit,
        timeout=5.0,
        sample_prompt="ping",
    )

    metadata = provider.metadata_json or {}
    metadata["model_validation"] = [r.model_dump() for r in results]
    provider.metadata_json = metadata
    db.add(provider)
    db.commit()
    db.refresh(provider)

    return results


@router.get(
    "/admin/providers/{provider_id}/tests",
    response_model=list[ProviderTestResult],
)
def admin_list_provider_tests_endpoint(
    provider_id: str,
    limit: int = Query(20, ge=1, le=100, description="返回最近的测试记录条数"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderTestResult]:
    """获取 Provider 最近的测试记录。"""

    _ensure_admin(current_user)
    try:
        records = list_test_records(db, provider_id, limit=limit)
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    provider = db.execute(
        select(Provider).where(Provider.provider_id == provider_id)
    ).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")
    return [_to_test_result(provider, r) for r in records if r is not None]


@router.get(
    "/admin/providers/{provider_id}/audit-logs",
    response_model=list[ProviderAuditLogResponse],
)
def admin_list_provider_audit_logs_endpoint(
    provider_id: str,
    limit: int = Query(50, ge=1, le=200, description="返回最近的审核日志条数"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[ProviderAuditLogResponse]:
    """获取 Provider 的审核与运营日志。"""

    _ensure_admin(current_user)
    try:
        logs = list_audit_logs(db, provider_id, limit=limit)
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    return [
        ProviderAuditLogResponse(
            id=log.id,
            provider_id=provider_id,
            action=log.action,
            from_status=log.from_status,
            to_status=log.to_status,
            operation_from_status=log.operation_from_status,
            operation_to_status=log.operation_to_status,
            operator_id=log.operator_id,
            remark=log.remark,
            test_record_id=log.test_record_uuid,
            created_at=log.created_at,
            updated_at=log.updated_at,
        )
        for log in logs
    ]


@router.post(
    "/admin/providers/{provider_id}/approve",
    response_model=AdminProviderResponse,
)
def admin_approve_provider_endpoint(
    provider_id: str,
    payload: ProviderAuditActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """审核通过 Provider。"""

    _ensure_admin(current_user)
    try:
        provider = approve_provider(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            remark=payload.remark if payload else None,
            limited=False,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    return _build_admin_provider_response(db, provider)


@router.post(
    "/admin/providers/{provider_id}/approve-limited",
    response_model=AdminProviderResponse,
)
def admin_approve_limited_provider_endpoint(
    provider_id: str,
    payload: ProviderAuditActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """审核限速通过 Provider。"""

    _ensure_admin(current_user)
    try:
        provider = approve_provider(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            remark=payload.remark if payload else None,
            limited=True,
            limit_qps=payload.limit_qps if payload else None,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    return _build_admin_provider_response(db, provider)


@router.post(
    "/admin/providers/{provider_id}/reject",
    response_model=AdminProviderResponse,
)
def admin_reject_provider_endpoint(
    provider_id: str,
    payload: ProviderAuditActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """拒绝 Provider。"""

    _ensure_admin(current_user)
    if payload is None or not payload.remark:
        raise bad_request("拒绝操作必须填写原因")
    try:
        provider = reject_provider(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            remark=payload.remark,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    return _build_admin_provider_response(db, provider)


@router.post(
    "/admin/providers/{provider_id}/pause",
    response_model=AdminProviderResponse,
)
def admin_pause_provider_endpoint(
    provider_id: str,
    payload: ProviderAuditActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """暂停 Provider 运营状态。"""

    _ensure_admin(current_user)
    try:
        provider = update_operation_status(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            "paused",
            remark=payload.remark if payload else None,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    except ProviderAuditError as exc:
        raise bad_request(str(exc))
    return _build_admin_provider_response(db, provider)


@router.post(
    "/admin/providers/{provider_id}/resume",
    response_model=AdminProviderResponse,
)
def admin_resume_provider_endpoint(
    provider_id: str,
    payload: ProviderAuditActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """恢复 Provider 运营状态到 active。"""

    _ensure_admin(current_user)
    try:
        provider = update_operation_status(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            "active",
            remark=payload.remark if payload else None,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    except ProviderAuditError as exc:
        raise bad_request(str(exc))
    return _build_admin_provider_response(db, provider)


@router.post(
    "/admin/providers/{provider_id}/offline",
    response_model=AdminProviderResponse,
)
def admin_offline_provider_endpoint(
    provider_id: str,
    payload: ProviderAuditActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> AdminProviderResponse:
    """下线 Provider，标记运营状态为 offline。"""

    _ensure_admin(current_user)
    try:
        provider = update_operation_status(
            db,
            provider_id,
            UUID(current_user.id) if current_user.id else None,
            "offline",
            remark=payload.remark if payload else None,
        )
    except ProviderNotFoundError:
        raise not_found(f"Provider '{provider_id}' not found")
    except ProviderAuditError as exc:
        raise bad_request(str(exc))
    return _build_admin_provider_response(db, provider)


@router.get(
    "/admin/providers/{provider_id}/models/{model_id:path}/pricing",
    response_model=ProviderModelPricingResponse,
)
def get_provider_model_pricing_endpoint(
    provider_id: str = Path(..., description="Provider 的短 ID，例如 moonshot-xxx"),
    model_id: str = Path(..., description="上游模型 ID，例如 gpt-4o"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelPricingResponse:
    """
    获取指定 provider+model 的计费配置。

    注意：该接口仅查询数据库中的 provider_models.pricing 字段，
    不会触及 Redis 中的 /models 缓存。
    """

    _ensure_admin(current_user)

    stmt_provider: Select[tuple[Provider]] = select(Provider).where(
        Provider.provider_id == provider_id
    )
    provider = db.execute(stmt_provider).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")

    stmt_model: Select[tuple[ProviderModel]] = select(ProviderModel).where(
        ProviderModel.provider_id == provider.id,
        ProviderModel.model_id == model_id,
    )
    model = db.execute(stmt_model).scalars().first()
    if model is None:
        # 当 provider_models 中尚未有该模型行时，视为“尚未配置定价”，返回空配置而不是 404，
        # 便于前端直接打开编辑对话框。
        return ProviderModelPricingResponse(
            provider_id=provider.provider_id,
            model_id=model_id,
            pricing=None,
        )

    return ProviderModelPricingResponse(
        provider_id=provider.provider_id,
        model_id=model.model_id,
        pricing=model.pricing or None,
    )


@router.put(
    "/admin/providers/{provider_id}/models/{model_id:path}/pricing",
    response_model=ProviderModelPricingResponse,
)
def update_provider_model_pricing_endpoint(
    provider_id: str = Path(..., description="Provider 的短 ID，例如 moonshot-xxx"),
    model_id: str = Path(..., description="上游模型 ID，例如 gpt-4o"),
    payload: ModelPricingUpdateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelPricingResponse:
    """
    更新指定 provider+model 的计费配置（每 1000 tokens 消耗的积分数）。

    行为：
    - 若 provider 或 model 不存在，则返回 404；
    - 只更新 input/output 中显式提供的字段；
    - 当 payload 为空或两个字段均为 None 时，清空现有 pricing。
    """

    _ensure_admin(current_user)

    stmt_provider: Select[tuple[Provider]] = select(Provider).where(
        Provider.provider_id == provider_id
    )
    provider = db.execute(stmt_provider).scalars().first()
    if provider is None:
        raise not_found(f"Provider '{provider_id}' not found")

    stmt_model: Select[tuple[ProviderModel]] = select(ProviderModel).where(
        ProviderModel.provider_id == provider.id,
        ProviderModel.model_id == model_id,
    )
    model = db.execute(stmt_model).scalars().first()
    if model is None:
        # 若 provider_models 中尚无该模型行，则以保守默认值创建一行，方便后续计费和同步。
        model = ProviderModel(
            provider_id=provider.id,
            model_id=model_id,
            family=model_id[:50],
            display_name=model_id[:100],
            context_length=8192,
            capabilities=["chat"],
            pricing=None,
            metadata_json=None,
            meta_hash=None,
        )
        db.add(model)
        db.flush()

    existing = model.pricing if isinstance(model.pricing, dict) else {}
    new_pricing: dict[str, float] = dict(existing)

    if payload is None or (
        payload.input is None and payload.output is None
    ):
        # 明确清空 pricing
        new_pricing = {}
    else:
        if payload.input is not None:
            new_pricing["input"] = float(payload.input)
        if payload.output is not None:
            new_pricing["output"] = float(payload.output)

    model.pricing = new_pricing or None
    db.add(model)
    db.commit()
    db.refresh(model)

    return ProviderModelPricingResponse(
        provider_id=provider.provider_id,
        model_id=model.model_id,
        pricing=model.pricing or None,
    )


__all__ = ["router"]
