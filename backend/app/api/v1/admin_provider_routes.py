from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import Provider, ProviderModel
from app.schemas import (
    AdminProviderResponse,
    AdminProvidersResponse,
    ModelPricingUpdateRequest,
    ProviderModelPricingResponse,
    ProviderVisibilityUpdateRequest,
)

router = APIRouter(
    tags=["admin-providers"],
    dependencies=[Depends(require_jwt_token)],
)


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")


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
        providers=[AdminProviderResponse.model_validate(p) for p in providers],
        total=len(providers),
    )


@router.put(
    "/admin/providers/{provider_id}/visibility",
    response_model=AdminProviderResponse,
)
def update_provider_visibility_endpoint(
    provider_id: str,
    payload: ProviderVisibilityUpdateRequest,
    db: Session = Depends(get_db),
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
    return AdminProviderResponse.model_validate(provider)


@router.get(
    "/admin/providers/{provider_id}/models/{model_id}/pricing",
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
    "/admin/providers/{provider_id}/models/{model_id}/pricing",
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
