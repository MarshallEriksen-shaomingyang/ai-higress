from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_http_client, get_redis
from app.errors import not_found
from app.jwt_auth import require_jwt_token
from app.logging_config import logger
from app.models import Provider, ProviderModel
from app.schemas import ProviderAPIKey, ProviderConfig, RoutingMetrics
from app.schemas.provider_routes import (
    ProviderMetricsResponse,
    ProviderModelsResponse,
    ProvidersResponse,
)
from app.provider.config import get_provider_config, load_provider_configs
from app.provider.discovery import ensure_provider_models_cached
from app.provider.health import HealthStatus
from app.services.provider_health_service import get_health_status_with_fallback
from app.storage.redis_service import get_routing_metrics

router = APIRouter(
    tags=["providers"],
    dependencies=[Depends(require_jwt_token)],
)


def _mask_secret(value: str, prefix: int = 4, suffix: int = 4) -> str:
    """
    对敏感字符串做脱敏，只保留前后若干位，其余用 * 替换。

    - 当字符串长度不足 prefix + suffix 时，仅保留首字符，其余全部打码。
    """
    if not value:
        return value

    length = len(value)
    if length <= prefix + suffix:
        # "a****" / "sk***"
        return value[0] + "*" * (length - 1)

    return f"{value[:prefix]}***{value[-suffix:]}"


def _sanitize_provider_config(cfg: ProviderConfig) -> ProviderConfig:
    """
    返回一个脱敏后的 ProviderConfig：
    - api_key / api_keys[*].key 仅保留前后几位，避免在 API 响应中暴露完整密钥。
    - 其它字段保持不变。
    """
    masked_api_key: str | None = None
    if cfg.api_key:
        masked_api_key = _mask_secret(cfg.api_key)

    masked_api_keys: list[ProviderAPIKey] | None = None
    if cfg.api_keys:
        masked_api_keys = [
            ProviderAPIKey(
                key=_mask_secret(item.key),
                weight=item.weight,
                max_qps=item.max_qps,
                label=item.label,
            )
            for item in cfg.api_keys
        ]

    return cfg.model_copy(update={"api_key": masked_api_key, "api_keys": masked_api_keys})


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers() -> ProvidersResponse:
    """Return all configured providers stored in the database."""
    providers = load_provider_configs()
    sanitized = [_sanitize_provider_config(p) for p in providers]
    return ProvidersResponse(providers=sanitized, total=len(sanitized))


@router.get("/providers/{provider_id}", response_model=ProviderConfig)
async def get_provider(provider_id: str) -> ProviderConfig:
    """Return configuration of a single provider."""
    cfg = get_provider_config(provider_id)
    if cfg is None:
        raise not_found(f"Provider '{provider_id}' not found")
    return _sanitize_provider_config(cfg)


def _sync_provider_models_to_db(
    db: Session, provider_id_slug: str, items: list[dict[str, Any]]
) -> None:
    """
    将 Redis 缓存中的模型列表尽量同步到 provider_models 表中。

    设计原则：
    - 只做「增量创建 / 更新」，不删除旧记录，以免覆盖人工配置；
    - 若 Provider 不存在或出现异常，仅记录日志，不影响主流程。
    """
    try:
        provider = (
            db.execute(
                select(Provider).where(Provider.provider_id == provider_id_slug)
            )
            .scalars()
            .first()
        )
        if provider is None:
            logger.warning(
                "sync_provider_models_to_db: provider %s not found, skip sync",
                provider_id_slug,
            )
            return

        existing_rows = (
            db.execute(
                select(ProviderModel).where(ProviderModel.provider_id == provider.id)
            )
            .scalars()
            .all()
        )
        existing_by_model_id: dict[str, ProviderModel] = {
            row.model_id: row for row in existing_rows
        }

        for raw in items:
            model_id = raw.get("model_id") or raw.get("id")
            if not isinstance(model_id, str):
                continue

            family = str(raw.get("family") or model_id)[:50]
            display_name = str(raw.get("display_name") or model_id)[:100]
            context_length = raw.get("context_length") or 8192
            try:
                context_length_int = int(context_length)
            except (TypeError, ValueError):
                context_length_int = 8192

            capabilities = raw.get("capabilities") or []
            pricing = raw.get("pricing")
            metadata = raw.get("metadata")
            meta_hash = raw.get("meta_hash")

            row = existing_by_model_id.get(model_id)
            if row is None:
                row = ProviderModel(
                    provider_id=provider.id,
                    model_id=model_id,
                    family=family,
                    display_name=display_name,
                    context_length=context_length_int,
                    capabilities=capabilities,
                    pricing=pricing,
                    metadata_json=metadata,
                    meta_hash=meta_hash,
                )
                db.add(row)
                existing_by_model_id[model_id] = row
            else:
                row.family = family
                row.display_name = display_name
                row.context_length = context_length_int
                row.capabilities = capabilities
                # 若已有人为配置的 pricing，则不覆盖；否则可从缓存补充默认值。
                if row.pricing is None and isinstance(pricing, dict):
                    row.pricing = pricing
                row.metadata_json = metadata
                row.meta_hash = meta_hash

        db.commit()
    except Exception:
        # 防御性日志，不影响 /providers/{id}/models 接口的正常返回。
        logger.exception(
            "Failed to sync provider_models for provider=%s from /providers/{id}/models response",
            provider_id_slug,
        )


@router.get("/providers/{provider_id}/models", response_model=ProviderModelsResponse)
async def get_provider_models(
    provider_id: str,
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
) -> ProviderModelsResponse:
    """
    Return the list of models for a provider, refreshing from upstream on cache miss.
    """
    cfg = get_provider_config(provider_id)
    if cfg is None:
        raise not_found(f"Provider '{provider_id}' not found")

    items = await ensure_provider_models_cached(client, redis, cfg)

    # 后台异步写库：将发现到的模型信息同步到 provider_models 表中。
    # 若写库失败，仅记录日志，不影响主流程。
    _sync_provider_models_to_db(db, provider_id, items)

    # 覆盖定价：使用数据库中 provider_models.pricing 的值，确保管理端修改后列表能立即反映。
    try:
        provider_row = (
            db.execute(select(Provider).where(Provider.provider_id == provider_id))
            .scalars()
            .first()
        )
        if provider_row is not None:
            model_rows = (
                db.execute(
                    select(ProviderModel).where(
                        ProviderModel.provider_id == provider_row.id,
                    )
                )
                .scalars()
                .all()
            )
            pricing_by_model_id: dict[str, dict[str, float]] = {
                row.model_id: row.pricing  # type: ignore[assignment]
                for row in model_rows
                if isinstance(row.pricing, dict)
            }
            if pricing_by_model_id:
                for item in items:
                    model_id = item.get("model_id") or item.get("id")
                    if isinstance(model_id, str) and model_id in pricing_by_model_id:
                        item["pricing"] = pricing_by_model_id[model_id]
    except Exception:
        # 防御性日志：覆盖计费失败不影响主逻辑，仅记录日志以便排查。
        logger.exception(
            "Failed to merge DB pricing into /providers/%s/models response",
            provider_id,
        )

    return ProviderModelsResponse(models=items, total=len(items))


@router.get("/providers/{provider_id}/health", response_model=HealthStatus)
async def get_provider_health(
    provider_id: str,
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
) -> HealthStatus:
    """
    Perform a lightweight health check for the given provider.
    """
    status = await get_health_status_with_fallback(redis, db, provider_id)
    if status is None:
        raise not_found(f"Provider '{provider_id}' not found")
    return status


@router.get("/providers/{provider_id}/metrics", response_model=ProviderMetricsResponse)
async def get_provider_metrics(
    provider_id: str,
    logical_model: str | None = Query(
        default=None,
        description="Optional logical model filter",
    ),
    redis: Redis = Depends(get_redis),
) -> ProviderMetricsResponse:
    """
    Return routing metrics for a provider.

    When `logical_model` is provided, we return at most one entry; for
    now we do not scan Redis for all logical models and simply return
    an empty list when the metrics key is missing.
    """
    cfg = get_provider_config(provider_id)
    if cfg is None:
        raise not_found(f"Provider '{provider_id}' not found")

    metrics_list: list[RoutingMetrics] = []
    if logical_model:
        metrics = await get_routing_metrics(redis, logical_model, provider_id)
        if metrics is not None:
            metrics_list.append(metrics)
    else:
        logger.info(
            "Provider metrics requested for %s without logical_model; returning empty list",
            provider_id,
        )

    return ProviderMetricsResponse(metrics=metrics_list)


__all__ = ["router"]

