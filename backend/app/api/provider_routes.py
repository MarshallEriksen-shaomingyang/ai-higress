from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_http_client, get_redis
from app.errors import bad_request, forbidden, http_error, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.model_cache import MODELS_CACHE_KEY
from app.models import Provider, ProviderModel, ProviderSubmission
from app.provider.config import get_provider_config, load_provider_configs
from app.provider.discovery import ensure_provider_models_cached
from app.provider.health import HealthStatus
from app.provider.sdk_selector import list_registered_sdk_vendors
from app.schemas import (
    ModelAliasUpdateRequest,
    ModelCapabilitiesUpdateRequest,
    ModelDisableUpdateRequest,
    ModelTTSRequirementsUpdateRequest,
    ProviderAPIKey,
    ProviderConfig,
    ProviderModelAliasResponse,
    ProviderModelCapabilitiesResponse,
    ProviderModelDisabledResponse,
    ProviderModelTTSRequirementsResponse,
    ProviderSubmissionStatus,
    RoutingMetrics,
)
from app.schemas.provider_routes import (
    ProviderMetricsResponse,
    ProviderModelsResponse,
    ProvidersResponse,
    SDKVendorsResponse,
)
from app.services.provider_health_service import get_health_status_with_fallback
from app.services.user_provider_service import get_accessible_provider_ids
from app.storage.redis_service import get_all_provider_metrics, get_routing_metrics

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


def _get_latest_submission_status(
    db: Session,
    provider_slug: str,
    owner_id: UUID | None,
    current_user_id: UUID,
    is_superuser: bool,
) -> ProviderSubmissionStatus | None:
    """
    查询当前用户最近一次投稿的状态，仅限提供商所有者或超级管理员查看。
    """
    if owner_id is None:
        return None
    if owner_id != current_user_id and not is_superuser:
        return None

    submission = (
        db.execute(
            select(ProviderSubmission)
            .where(ProviderSubmission.provider_id == provider_slug)
            .where(ProviderSubmission.user_id == owner_id)
            .order_by(ProviderSubmission.created_at.desc())
        )
        .scalars()
        .first()
    )
    if submission is None:
        return None

    return ProviderSubmissionStatus(
        id=submission.id,
        approval_status=submission.approval_status,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


def _ensure_can_edit_provider_models(
    db: Session,
    provider_id_slug: str,
    current_user: AuthenticatedUser,
) -> Provider:
    """
    确保当前用户有权限修改指定 Provider 下的模型配置（计费 / 映射等）。

    - 超级管理员：可以管理所有 Provider；
    - 普通用户：仅能管理自己私有/受限 Provider（visibility=private/restricted 且 owner_id 匹配）。
    """
    # 超级管理员直接放行
    if current_user.is_superuser:
        provider = (
            db.execute(select(Provider).where(Provider.provider_id == provider_id_slug))
            .scalars()
            .first()
        )
        if provider is None:
            raise not_found(f"Provider '{provider_id_slug}' not found")
        return provider

    provider = (
        db.execute(select(Provider).where(Provider.provider_id == provider_id_slug))
        .scalars()
        .first()
    )
    if provider is None:
        raise not_found(f"Provider '{provider_id_slug}' not found")

    if (
        getattr(provider, "visibility", "public") in {"private", "restricted"}
        and provider.owner_id is not None
        and str(provider.owner_id) == current_user.id
    ):
        return provider

    raise forbidden("只有提供商所有者或超级管理员可以修改该提供商的模型配置")


@router.get("/providers/sdk-vendors", response_model=SDKVendorsResponse)
async def list_supported_sdk_vendors() -> SDKVendorsResponse:
    vendors = list_registered_sdk_vendors()
    return SDKVendorsResponse(vendors=vendors, total=len(vendors))


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProvidersResponse:
    """Return all configured providers stored in the database."""
    providers = load_provider_configs(
        session=db,
        user_id=UUID(current_user.id),
        is_superuser=current_user.is_superuser,
    )
    sanitized = [_sanitize_provider_config(p) for p in providers]
    return ProvidersResponse(providers=sanitized, total=len(sanitized))


@router.get("/providers/{provider_id}", response_model=ProviderConfig)
async def get_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderConfig:
    """Return configuration of a single provider."""
    if not current_user.is_superuser:
        allowed = get_accessible_provider_ids(db, UUID(current_user.id))
        if provider_id not in allowed:
            raise forbidden("无权查看该提供商配置")
    cfg = get_provider_config(provider_id, session=db)
    if cfg is None:
        raise not_found(f"Provider '{provider_id}' not found")
    sanitized = _sanitize_provider_config(cfg)
    provider_row = (
        db.execute(select(Provider).where(Provider.provider_id == provider_id))
        .scalars()
        .first()
    )
    owner_uuid = provider_row.owner_id if provider_row else None
    latest_submission = _get_latest_submission_status(
        db=db,
        provider_slug=provider_id,
        owner_id=owner_uuid,
        current_user_id=UUID(current_user.id),
        is_superuser=current_user.is_superuser,
    )
    if latest_submission:
        sanitized = sanitized.model_copy(update={"latest_submission": latest_submission})
    return sanitized


def _sync_provider_models_to_db(
    db: Session, provider_id_slug: str, items: list[dict[str, Any]]
) -> bool:
    """
    将 Redis 缓存中的模型列表尽量同步到 provider_models 表中。

    设计原则：
    - 只做「增量创建 / 更新」，不删除旧记录，以免覆盖人工配置；
    - 若 Provider 不存在或出现异常，仅记录日志，不影响主流程。
    """
    logical_models_changed = False
    db_changed = False
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
            return False

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
                db_changed = True
                logical_models_changed = True
            else:
                gateway_meta: dict[str, Any] | None = None
                existing_meta = getattr(row, "metadata_json", None)
                if isinstance(existing_meta, dict) and isinstance(existing_meta.get("_gateway"), dict):
                    gateway_meta = dict(existing_meta.get("_gateway") or {})
                    override = gateway_meta.get("capabilities_override")
                    if isinstance(override, list):
                        capabilities = override

                if row.display_name != display_name:
                    logical_models_changed = True
                if list(getattr(row, "capabilities") or []) != list(capabilities or []):
                    logical_models_changed = True
                if getattr(row, "meta_hash", None) != meta_hash:
                    logical_models_changed = True

                if row.family != family:
                    db_changed = True
                if row.display_name != display_name:
                    db_changed = True
                if row.context_length != context_length_int:
                    db_changed = True
                if list(getattr(row, "capabilities") or []) != list(capabilities or []):
                    db_changed = True
                if getattr(row, "meta_hash", None) != meta_hash:
                    db_changed = True

                row.family = family
                row.display_name = display_name
                row.context_length = context_length_int
                row.capabilities = capabilities
                # 若已有人为配置的 pricing，则不覆盖；否则可从缓存补充默认值。
                if row.pricing is None and isinstance(pricing, dict):
                    row.pricing = pricing
                    db_changed = True
                if gateway_meta:
                    if isinstance(metadata, dict):
                        merged = dict(metadata)
                        merged["_gateway"] = gateway_meta
                        if row.metadata_json != merged:
                            db_changed = True
                        row.metadata_json = merged
                    else:
                        merged = {"_gateway": gateway_meta, "upstream": metadata}
                        if row.metadata_json != merged:
                            db_changed = True
                        row.metadata_json = merged
                else:
                    if row.metadata_json != metadata:
                        db_changed = True
                    row.metadata_json = metadata
                row.meta_hash = meta_hash

        if db_changed:
            db.commit()
        else:
            db.rollback()
        return logical_models_changed
    except Exception:
        # 防御性日志，不影响 /providers/{id}/models 接口的正常返回。
        logger.exception(
            "Failed to sync provider_models for provider=%s from /providers/{id}/models response",
            provider_id_slug,
        )
        return False


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
    cfg = get_provider_config(provider_id, session=db)
    if cfg is None:
        raise not_found(f"Provider '{provider_id}' not found")

    try:
        items = await ensure_provider_models_cached(client, redis, cfg)
    except Exception as exc:
        upstream_status_code: int | None = None
        upstream_url: str | None = None

        if isinstance(exc, httpx.HTTPError):
            if isinstance(exc, httpx.HTTPStatusError):
                upstream_status_code = getattr(exc.response, "status_code", None)
                req = getattr(exc, "request", None)
                if req is not None and getattr(req, "url", None) is not None:
                    upstream_url = str(req.url)
            else:
                req = getattr(exc, "request", None)
                if req is not None and getattr(req, "url", None) is not None:
                    upstream_url = str(req.url)

        if upstream_status_code == 404:
            message = (
                "无法获取该 Provider 的模型列表：上游 /models 返回 404。"
                "请检查 base_url/models_path 是否正确，或配置 static_models 以跳过远端发现。"
            )
        else:
            message = (
                "无法获取该 Provider 的模型列表：上游模型发现失败。"
                "请稍后重试，或配置 static_models 以跳过远端发现。"
            )

        logger.warning(
            "Provider %s: models discovery failed (status=%s, url=%s): %s",
            provider_id,
            upstream_status_code,
            upstream_url,
            exc,
        )

        raise http_error(
            status.HTTP_502_BAD_GATEWAY,
            error="provider_models_discovery_failed",
            message=message,
            details={
                "provider_id": provider_id,
                "upstream_status_code": upstream_status_code,
                "upstream_url": upstream_url,
            },
        )

    # 后台异步写库：将发现到的模型信息同步到 provider_models 表中。
    # 若写库失败，仅记录日志，不影响主流程。
    logical_models_changed = _sync_provider_models_to_db(db, provider_id, items)
    if logical_models_changed and hasattr(redis, "delete"):
        try:
            from app.services.logical_model_sync import sync_logical_models

            await sync_logical_models(redis, session=db, provider_ids=[provider_id])
        except Exception:
            logger.warning(
                "Failed to sync logical models after syncing provider_models for provider=%s",
                provider_id,
                exc_info=True,
            )

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
            alias_by_model_id: dict[str, str] = {
                row.model_id: row.alias  # type: ignore[assignment]
                for row in model_rows
                if isinstance(getattr(row, "alias", None), str)
                and getattr(row, "alias", "").strip()
            }
            capabilities_by_model_id: dict[str, list[Any]] = {
                row.model_id: list(getattr(row, "capabilities") or [])
                for row in model_rows
                if isinstance(getattr(row, "capabilities", None), list)
                and getattr(row, "capabilities") is not None
            }
            disabled_by_model_id: dict[str, bool] = {
                row.model_id: True
                for row in model_rows
                if bool(getattr(row, "disabled", False))
            }
            if pricing_by_model_id:
                for item in items:
                    model_id = item.get("model_id") or item.get("id")
                    if isinstance(model_id, str) and model_id in pricing_by_model_id:
                        item["pricing"] = pricing_by_model_id[model_id]
            if alias_by_model_id:
                for item in items:
                    model_id = item.get("model_id") or item.get("id")
                    if isinstance(model_id, str) and model_id in alias_by_model_id:
                        item["alias"] = alias_by_model_id[model_id]
            if capabilities_by_model_id:
                for item in items:
                    model_id = item.get("model_id") or item.get("id")
                    if isinstance(model_id, str) and model_id in capabilities_by_model_id:
                        item["capabilities"] = capabilities_by_model_id[model_id]
            if disabled_by_model_id:
                for item in items:
                    model_id = item.get("model_id") or item.get("id")
                    if isinstance(model_id, str):
                        item["disabled"] = bool(disabled_by_model_id.get(model_id, False))
            else:
                for item in items:
                    model_id = item.get("model_id") or item.get("id")
                    if isinstance(model_id, str):
                        item["disabled"] = False
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
    返回 Provider 最近一次健康状态（由探针/巡检写入 DB + Redis 缓存）。
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
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ProviderMetricsResponse:
    """
    返回 provider 的路由指标。

    - 当提供 `logical_model` 参数时，返回该 provider 在指定逻辑模型下的指标（最多一条）
    - 当不提供 `logical_model` 参数时，返回该 provider 在所有逻辑模型下的指标列表
    """
    cfg = get_provider_config(provider_id, session=db)
    if cfg is None:
        raise not_found(f"Provider '{provider_id}' not found")

    metrics_list: list[RoutingMetrics] = []
    if logical_model:
        # 查询特定逻辑模型的指标
        metrics = await get_routing_metrics(redis, logical_model, provider_id)
        if metrics is not None:
            metrics_list.append(metrics)
    else:
        # 查询所有逻辑模型的指标
        metrics_list = await get_all_provider_metrics(redis, provider_id)
        logger.info(
            "Provider metrics requested for %s without logical_model; returning %d metrics",
            provider_id,
            len(metrics_list),
        )

    return ProviderMetricsResponse(metrics=metrics_list)


@router.get(
    "/providers/{provider_id}/models/{model_id:path}/mapping",
    response_model=ProviderModelAliasResponse,
)
def get_provider_model_mapping(
    provider_id: str,
    model_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelAliasResponse:
    """
    获取指定 provider+model 的别名映射配置。

    - 当 provider_models 中尚未有该模型行或未配置别名时，返回 alias=None；
    - 仅允许超级管理员或该私有 Provider 的所有者访问。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)

    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    if model_row is None:
        return ProviderModelAliasResponse(
            provider_id=provider_row.provider_id,
            model_id=model_id,
            alias=None,
        )

    return ProviderModelAliasResponse(
        provider_id=provider_row.provider_id,
        model_id=model_row.model_id,
        alias=getattr(model_row, "alias", None),
    )


@router.put(
    "/providers/{provider_id}/models/{model_id:path}/mapping",
    response_model=ProviderModelAliasResponse,
)
def update_provider_model_mapping(
    provider_id: str,
    model_id: str,
    payload: ModelAliasUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelAliasResponse:
    """
    更新指定 provider+model 的别名映射配置。

    行为：
    - 若 provider 或 model 不存在，则返回 404；
    - alias 为空或仅包含空白字符时，清空现有别名；
    - alias 非空时，为避免歧义，不允许同一 Provider 下多个模型使用相同别名。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)

    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    if model_row is None:
        # 若 provider_models 中尚无该模型行，则以保守默认值创建一行，方便后续管理。
        model_row = ProviderModel(
            provider_id=provider_row.id,
            model_id=model_id,
            family=model_id[:50],
            display_name=model_id[:100],
            context_length=8192,
            capabilities=["chat"],
            pricing=None,
            metadata_json=None,
            meta_hash=None,
        )
        db.add(model_row)
        db.flush()

    # 归一化别名：空串视为清空。
    new_alias = (payload.alias or "").strip() if payload and payload.alias is not None else None
    if new_alias == "":
        new_alias = None

    if new_alias is not None:
        # 确保同一 Provider 下别名唯一，避免路由歧义。
        conflict = (
            db.execute(
                select(ProviderModel).where(
                    ProviderModel.provider_id == provider_row.id,
                    ProviderModel.model_id != model_id,
                    ProviderModel.alias == new_alias,
                )
            )
            .scalars()
            .first()
        )
        if conflict is not None:
            raise bad_request(
                f"别名 '{new_alias}' 已被模型 '{conflict.model_id}' 使用，请选择其他别名。",
            )

    model_row.alias = new_alias
    db.add(model_row)
    db.commit()
    db.refresh(model_row)

    return ProviderModelAliasResponse(
        provider_id=provider_row.provider_id,
        model_id=model_row.model_id,
        alias=model_row.alias,
    )


def _apply_gateway_capabilities_override(
    model_row: ProviderModel, capabilities: list[str]
) -> None:
    """
    Persist gateway-managed overrides into metadata_json under reserved key `_gateway`.
    """
    existing = getattr(model_row, "metadata_json", None)
    gateway: dict[str, Any] = {}
    if isinstance(existing, dict) and isinstance(existing.get("_gateway"), dict):
        gateway = dict(existing.get("_gateway") or {})
    gateway["capabilities_override"] = capabilities
    if isinstance(existing, dict):
        merged = dict(existing)
        merged["_gateway"] = gateway
        model_row.metadata_json = merged
    else:
        model_row.metadata_json = {"_gateway": gateway, "upstream": existing}


def _apply_gateway_tts_requires_reference_audio_override(
    model_row: ProviderModel, *, requires_reference_audio: bool
) -> None:
    """
    Persist gateway-managed TTS requirements into metadata_json under reserved key `_gateway.tts`.
    """
    existing = getattr(model_row, "metadata_json", None)
    gateway: dict[str, Any] = {}
    if isinstance(existing, dict) and isinstance(existing.get("_gateway"), dict):
        gateway = dict(existing.get("_gateway") or {})
    tts: dict[str, Any] = {}
    if isinstance(gateway.get("tts"), dict):
        tts = dict(gateway.get("tts") or {})
    tts["requires_reference_audio"] = bool(requires_reference_audio)
    gateway["tts"] = tts
    if isinstance(existing, dict):
        merged = dict(existing)
        merged["_gateway"] = gateway
        model_row.metadata_json = merged
    else:
        model_row.metadata_json = {"_gateway": gateway, "upstream": existing}


@router.get(
    "/providers/{provider_id}/models/{model_id:path}/capabilities",
    response_model=ProviderModelCapabilitiesResponse,
)
def get_provider_model_capabilities(
    provider_id: str,
    model_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelCapabilitiesResponse:
    """
    获取指定 provider+model 的能力配置。

    - 仅允许超级管理员或该私有 Provider 的所有者访问；
    - 若 provider_models 中尚无该模型行，则返回空列表（表示未配置覆盖）。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)
    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    caps: list[Any] = []
    if model_row is not None and isinstance(getattr(model_row, "capabilities", None), list):
        caps = list(getattr(model_row, "capabilities") or [])
    return ProviderModelCapabilitiesResponse(
        provider_id=provider_row.provider_id,
        model_id=model_id,
        capabilities=caps,  # type: ignore[arg-type]
    )


@router.put(
    "/providers/{provider_id}/models/{model_id:path}/capabilities",
    response_model=ProviderModelCapabilitiesResponse,
)
async def update_provider_model_capabilities(
    provider_id: str,
    model_id: str,
    payload: ModelCapabilitiesUpdateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelCapabilitiesResponse:
    """
    更新指定 provider+model 的能力配置（覆盖上游 /models 返回的 capabilities）。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)

    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    if model_row is None:
        model_row = ProviderModel(
            provider_id=provider_row.id,
            model_id=model_id,
            family=model_id[:50],
            display_name=model_id[:100],
            context_length=8192,
            capabilities=["chat"],
            pricing=None,
            metadata_json=None,
            meta_hash=None,
        )
        db.add(model_row)
        db.flush()

    # 去重并保持顺序
    desired: list[str] = []
    for cap in payload.capabilities or []:
        value = getattr(cap, "value", None) or str(cap)
        if value and value not in desired:
            desired.append(value)
    model_row.capabilities = desired
    _apply_gateway_capabilities_override(model_row, desired)
    db.add(model_row)
    db.commit()
    db.refresh(model_row)

    # 缓存失效：/models 聚合缓存 + 逻辑模型缓存（llm:logical:*）增量刷新
    if hasattr(redis, "delete"):
        try:
            await redis.delete(MODELS_CACHE_KEY)  # type: ignore[attr-defined]
        except Exception:
            logger.warning("Failed to invalidate MODELS cache key", exc_info=True)

        try:
            from app.services.logical_model_sync import sync_logical_models

            await sync_logical_models(redis, session=db, provider_ids=[provider_id])
        except Exception:
            logger.warning(
                "Failed to sync logical models after updating capabilities for %s/%s",
                provider_id,
                model_id,
                exc_info=True,
            )

    return ProviderModelCapabilitiesResponse(
        provider_id=provider_row.provider_id,
        model_id=model_row.model_id,
        capabilities=desired,  # type: ignore[arg-type]
    )


@router.get(
    "/providers/{provider_id}/models/{model_id:path}/tts-requirements",
    response_model=ProviderModelTTSRequirementsResponse,
)
def get_provider_model_tts_requirements(
    provider_id: str,
    model_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelTTSRequirementsResponse:
    """
    获取指定 provider+model 的 TTS 约束/需求配置。

    - 仅允许超级管理员或该私有 Provider 的所有者访问；
    - 若 provider_models 中尚无该模型行或未配置 `_gateway.tts`，返回 requires_reference_audio=false。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)
    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    requires_reference_audio = False
    if model_row is not None:
        meta = getattr(model_row, "metadata_json", None)
        if isinstance(meta, dict):
            gateway = meta.get("_gateway")
            if isinstance(gateway, dict):
                tts = gateway.get("tts")
                if isinstance(tts, dict) and isinstance(tts.get("requires_reference_audio"), bool):
                    requires_reference_audio = bool(tts.get("requires_reference_audio"))

    return ProviderModelTTSRequirementsResponse(
        provider_id=provider_row.provider_id,
        model_id=model_id,
        requires_reference_audio=requires_reference_audio,
    )


@router.put(
    "/providers/{provider_id}/models/{model_id:path}/tts-requirements",
    response_model=ProviderModelTTSRequirementsResponse,
)
def update_provider_model_tts_requirements(
    provider_id: str,
    model_id: str,
    payload: ModelTTSRequirementsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelTTSRequirementsResponse:
    """
    更新指定 provider+model 的 TTS 约束/需求配置。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)
    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    if model_row is None:
        model_row = ProviderModel(
            provider_id=provider_row.id,
            model_id=model_id,
            family=model_id[:50],
            display_name=model_id[:100],
            context_length=8192,
            capabilities=["chat"],
            pricing=None,
            metadata_json=None,
            meta_hash=None,
        )
        db.add(model_row)
        db.flush()

    _apply_gateway_tts_requires_reference_audio_override(
        model_row, requires_reference_audio=bool(payload.requires_reference_audio)
    )
    db.add(model_row)
    db.commit()
    db.refresh(model_row)

    return ProviderModelTTSRequirementsResponse(
        provider_id=provider_row.provider_id,
        model_id=model_row.model_id,
        requires_reference_audio=bool(payload.requires_reference_audio),
    )


@router.get(
    "/providers/{provider_id}/models/{model_id:path}/disabled",
    response_model=ProviderModelDisabledResponse,
)
def get_provider_model_disabled(
    provider_id: str,
    model_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelDisabledResponse:
    """
    查询指定 provider+model 的禁用状态。

    仅允许超级管理员或该私有/受限 Provider 的所有者访问。
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)
    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    return ProviderModelDisabledResponse(
        provider_id=provider_row.provider_id,
        model_id=model_id,
        disabled=bool(getattr(model_row, "disabled", False)) if model_row else False,
    )


@router.put(
    "/providers/{provider_id}/models/{model_id:path}/disabled",
    response_model=ProviderModelDisabledResponse,
)
async def update_provider_model_disabled(
    provider_id: str,
    model_id: str,
    payload: ModelDisableUpdateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderModelDisabledResponse:
    """
    更新指定 provider+model 的禁用状态。

    - disabled=true：禁用该模型（不参与 /models 聚合与路由）
    - disabled=false：恢复启用
    """
    provider_row = _ensure_can_edit_provider_models(db, provider_id, current_user)

    model_row = (
        db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider_row.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    if model_row is None:
        # 若 provider_models 中尚无该模型行，则以保守默认值创建一行，方便后续管理。
        model_row = ProviderModel(
            provider_id=provider_row.id,
            model_id=model_id,
            family=model_id[:50],
            display_name=model_id[:100],
            context_length=8192,
            capabilities=["chat"],
            pricing=None,
            metadata_json=None,
            meta_hash=None,
            disabled=bool(payload.disabled),
        )
        db.add(model_row)
        db.flush()
    else:
        model_row.disabled = bool(payload.disabled)
        db.add(model_row)

    db.commit()
    db.refresh(model_row)

    # 缓存失效：/models 聚合缓存 + 逻辑模型缓存（llm:logical:*）增量刷新
    if redis is not object:
        try:
            await redis.delete(MODELS_CACHE_KEY)  # type: ignore[attr-defined]
        except Exception:
            logger.warning("Failed to invalidate MODELS cache key", exc_info=True)

        try:
            from app.services.logical_model_sync import sync_logical_models

            await sync_logical_models(redis, session=db, provider_ids=[provider_id])
        except Exception:
            logger.warning(
                "Failed to sync logical models after toggling disabled for %s/%s",
                provider_id,
                model_id,
                exc_info=True,
            )

    return ProviderModelDisabledResponse(
        provider_id=provider_row.provider_id,
        model_id=model_row.model_id,
        disabled=bool(model_row.disabled),
    )


__all__ = ["router"]
