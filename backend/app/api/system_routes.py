"""
系统管理API，用于密钥生成和系统初始化
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, load_only

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.models import GatewayConfig as GatewayConfigRow
from app.schemas.system import (
    CacheClearRequest,
    CacheClearResponse,
    CacheSegment,
    GatewayConfig,
    GatewayConfigUpdateRequest,
    KeyValidationRequest,
    KeyValidationResponse,
    ProviderLimitsResponse,
    ProviderLimitsUpdateRequest,
    SecretKeyGenerationRequest,
    SecretKeyResponse,
    SystemAdminInitRequest,
    SystemAdminInitResponse,
)
from app.services.key_management_service import (
    KeyManagementServiceError,
    generate_system_secret_key,
    initialize_system_admin,
    rotate_system_secret_key,
    validate_key_strength,
)
from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis

router = APIRouter(tags=["system"], prefix="/system")

def _is_gateway_config_schema_error(exc: Exception) -> bool:
    """
    检测 gateway_config 表/列缺失导致的 SQL 错误。

    说明：一些分支/环境可能尚未跑完迁移；/system/gateway-config 属于展示型接口，
    不应因为 schema 漂移而直接 500。
    """
    if not isinstance(exc, ProgrammingError):
        return False
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    if sqlstate in {"42P01", "42703"}:  # undefined_table / undefined_column
        return True
    msg = str(orig or exc).lower()
    return ("undefinedtable" in msg) or ("undefinedcolumn" in msg) or ("does not exist" in msg)


def _apply_gateway_config_to_settings(row: GatewayConfigRow) -> None:
    """
    将数据库中的网关配置同步到当前进程的 settings。

    - gateway_* 字段用于前端展示；
    - upstream_timeout / models_cache_ttl 则直接影响上游超时与模型缓存 TTL。
    """
    settings.gateway_api_base_url = row.api_base_url
    settings.gateway_max_concurrent_requests = row.max_concurrent_requests
    settings.gateway_request_timeout_ms = row.request_timeout_ms
    settings.gateway_cache_ttl_seconds = row.cache_ttl_seconds
    settings.probe_prompt = row.probe_prompt or settings.probe_prompt

    # 将毫秒级请求超时映射到内部 upstream_timeout（秒）。
    settings.upstream_timeout = row.request_timeout_ms / 1000.0
    # 将缓存 TTL 应用到模型缓存层。
    settings.models_cache_ttl = row.cache_ttl_seconds
    # Dashboard 指标留存天数（分钟桶）。
    settings.dashboard_metrics_retention_days = row.metrics_retention_days


def _get_or_create_gateway_config_row(db: Session) -> GatewayConfigRow:
    """
    从数据库获取当前网关配置，如不存在则根据 settings 中的默认值创建一条记录。
    """
    try:
        # 注意：旧 DB 可能缺少新增列（如 kb_global_embedding_model），这里避免 SELECT *。
        row = (
            db.execute(
                select(GatewayConfigRow).options(
                    # 仅加载 /system/gateway-config 需要的列，减少 schema 漂移导致的风险
                    # （缺列时会触发 ProgrammingError，后续会降级处理）。
                    # load_only 不会影响后续写入；写入失败则在 commit 处捕获并提示迁移。
                    load_only(
                        GatewayConfigRow.api_base_url,
                        GatewayConfigRow.max_concurrent_requests,
                        GatewayConfigRow.request_timeout_ms,
                        GatewayConfigRow.cache_ttl_seconds,
                        GatewayConfigRow.probe_prompt,
                        GatewayConfigRow.metrics_retention_days,
                    )
                )
            )
            .scalars()
            .first()
        )
    except ProgrammingError as exc:
        db.rollback()
        if _is_gateway_config_schema_error(exc):
            logger.warning("gateway_config schema not ready, fallback to settings defaults", exc_info=True)
            row = GatewayConfigRow(
                api_base_url=settings.gateway_api_base_url,
                max_concurrent_requests=settings.gateway_max_concurrent_requests,
                request_timeout_ms=settings.gateway_request_timeout_ms,
                cache_ttl_seconds=settings.gateway_cache_ttl_seconds,
                probe_prompt=settings.probe_prompt,
                metrics_retention_days=settings.dashboard_metrics_retention_days,
            )
            _apply_gateway_config_to_settings(row)
            return row
        raise

    if row is None:
        row = GatewayConfigRow(
            api_base_url=settings.gateway_api_base_url,
            max_concurrent_requests=settings.gateway_max_concurrent_requests,
            request_timeout_ms=settings.gateway_request_timeout_ms,
            cache_ttl_seconds=settings.gateway_cache_ttl_seconds,
            probe_prompt=settings.probe_prompt,
            metrics_retention_days=settings.dashboard_metrics_retention_days,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except ProgrammingError as exc:
            db.rollback()
            if _is_gateway_config_schema_error(exc):
                logger.warning("gateway_config schema not ready, skip DB write and use settings defaults", exc_info=True)
                row = GatewayConfigRow(
                    api_base_url=settings.gateway_api_base_url,
                    max_concurrent_requests=settings.gateway_max_concurrent_requests,
                    request_timeout_ms=settings.gateway_request_timeout_ms,
                    cache_ttl_seconds=settings.gateway_cache_ttl_seconds,
                    probe_prompt=settings.probe_prompt,
                    metrics_retention_days=settings.dashboard_metrics_retention_days,
                )
                _apply_gateway_config_to_settings(row)
                return row
            raise
    # 每次获取时都同步到 settings，确保进程内配置与数据库一致。
    _apply_gateway_config_to_settings(row)
    return row


async def _delete_pattern(redis: Redis, pattern: str) -> int:
    """
    删除匹配给定模式的所有键，返回删除的键数量。

    为了避免误删，这里仅用于维护接口中明确指定的缓存前缀。
    """
    # 单 key（无通配符）直接尝试删除
    if "*" not in pattern and "?" not in pattern and "[" not in pattern:
        exists = await redis.exists(pattern)  # type: ignore[attr-defined]
        if not exists:
            return 0
        await redis.delete(pattern)  # type: ignore[attr-defined]
        return 1

    keys = await redis.keys(pattern)  # type: ignore[attr-defined]
    if not keys:
        return 0
    # Redis 支持变参删除
    await redis.delete(*keys)  # type: ignore[arg-type,attr-defined]
    return len(keys)


@router.post("/secret-key/generate", response_model=SecretKeyResponse)
def generate_secret_key(
    request: SecretKeyGenerationRequest,
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> SecretKeyResponse:
    """
    生成系统主密钥
    
    Args:
        request: 密钥生成请求
        current_user: 当前认证用户
        
    Returns:
        生成的系统密钥
        
    Raises:
        HTTPException: 如果用户不是超级用户
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以生成系统密钥",
        )

    try:
        secret_key = generate_system_secret_key(request.length)
        logger.warning(f"System secret key generated by superuser {current_user.username}")
        return SecretKeyResponse(secret_key=secret_key)
    except KeyManagementServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate secret key: {exc!s}",
        )


@router.post("/admin/init", response_model=SystemAdminInitResponse)
def init_system_admin(
    request: SystemAdminInitRequest,
    db: Session = Depends(get_db),
) -> SystemAdminInitResponse:
    """
    初始化系统管理员账户
    
    Args:
        request: 初始化请求
        db: 数据库会话
        
    Returns:
        管理员凭证
        
    Raises:
        HTTPException: 如果系统已有用户或初始化失败
    """
    try:
        admin_credentials = initialize_system_admin(
            session=db,
            username=request.username,
            email=request.email,
            display_name=request.display_name,
        )

        return SystemAdminInitResponse(
            username=admin_credentials["username"],
            email=admin_credentials["email"],
            password=admin_credentials["password"],
        )
    except KeyManagementServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize system admin: {exc!s}",
        )


@router.post("/secret-key/rotate", response_model=SecretKeyResponse)
def rotate_secret_key(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> SecretKeyResponse:
    """
    轮换系统主密钥
    
    Warning: 这将使所有现有的密码哈希和API密钥失效！
    
    Args:
        current_user: 当前认证用户
        
    Returns:
        新生成的系统密钥
        
    Raises:
        HTTPException: 如果用户不是超级用户
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以轮换系统密钥",
        )

    try:
        new_key = rotate_system_secret_key()
        logger.error(f"System secret key rotation initiated by superuser {current_user.username}")
        return SecretKeyResponse(secret_key=new_key)
    except KeyManagementServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate secret key: {exc!s}",
        )


@router.post("/key/validate", response_model=KeyValidationResponse)
def validate_key(
    request: KeyValidationRequest,
) -> KeyValidationResponse:
    """
    验证密钥强度
    
    Args:
        request: 验证请求
        
    Returns:
        验证结果
    """
    is_valid = validate_key_strength(request.key)

    if is_valid:
        message = "密钥强度足够"
    else:
        message = "密钥强度不足，建议使用更长的随机密钥"

    return KeyValidationResponse(is_valid=is_valid, message=message)


@router.get("/provider-limits", response_model=ProviderLimitsResponse)
def get_provider_limits(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderLimitsResponse:
    """
    获取系统中与 Provider 相关的配额与审核配置。
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以查看提供商限制配置",
        )

    return ProviderLimitsResponse(
        default_user_private_provider_limit=settings.default_user_private_provider_limit,
        max_user_private_provider_limit=settings.max_user_private_provider_limit,
        require_approval_for_shared_providers=settings.require_approval_for_shared_providers,
    )


@router.get("/gateway-config", response_model=GatewayConfig)
def get_gateway_config(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db),
) -> GatewayConfig:
    """
    获取当前中转网关的基础配置信息。

    该信息会展示在前端首页，方便最终用户查看：
    - API Base URL：调用网关时使用的基础地址；
    - Max Concurrent Requests：网关建议/支持的最大并发请求数；
    - Request Timeout：推荐的单次请求超时时间；
    - Cache TTL：推荐的缓存 TTL，用于理解数据更新频率。
    """
    # 任何已登录用户均可查看网关配置，便于在文档页面展示。
    row = _get_or_create_gateway_config_row(db)
    return GatewayConfig(
        api_base_url=row.api_base_url,
        max_concurrent_requests=row.max_concurrent_requests,
        request_timeout_ms=row.request_timeout_ms,
        cache_ttl_seconds=row.cache_ttl_seconds,
        probe_prompt=row.probe_prompt or settings.probe_prompt,
        metrics_retention_days=row.metrics_retention_days,
    )


@router.put("/gateway-config", response_model=GatewayConfig)
def update_gateway_config(
    payload: GatewayConfigUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    db: Session = Depends(get_db),
) -> GatewayConfig:
    """
    更新中转网关的基础配置，并持久化到数据库中。

    注意：
    - 环境变量仅作为默认值，在首次创建记录时使用；
    - 之后的修改都会写入 gateway_config 表，并同步到当前进程的 settings；
    - 仅超级管理员可以修改。
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以更新网关配置",
        )

    row = _get_or_create_gateway_config_row(db)
    row.api_base_url = payload.api_base_url
    row.max_concurrent_requests = payload.max_concurrent_requests
    row.request_timeout_ms = payload.request_timeout_ms
    row.cache_ttl_seconds = payload.cache_ttl_seconds
    row.probe_prompt = payload.probe_prompt
    # 为了兼容旧前端（未携带该字段的 PUT 请求），仅在显式传入时才覆盖。
    payload_data = (
        payload.model_dump(exclude_unset=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_unset=True)  # type: ignore[attr-defined]
    )
    if "metrics_retention_days" in payload_data:
        row.metrics_retention_days = payload.metrics_retention_days

    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except ProgrammingError as exc:
        db.rollback()
        if _is_gateway_config_schema_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="gateway_config 数据表结构未就绪，请先运行数据库迁移（alembic upgrade head）",
            ) from exc
        raise

    # 同步到当前进程内的 settings，便于其它代码复用。
    _apply_gateway_config_to_settings(row)

    return GatewayConfig(
        api_base_url=row.api_base_url,
        max_concurrent_requests=row.max_concurrent_requests,
        request_timeout_ms=row.request_timeout_ms,
        cache_ttl_seconds=row.cache_ttl_seconds,
        probe_prompt=row.probe_prompt,
        metrics_retention_days=row.metrics_retention_days,
    )


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_cache(
    payload: CacheClearRequest,
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    redis: Redis = Depends(get_redis),
) -> CacheClearResponse:
    """
    清理网关相关的缓存键，仅供超级管理员使用。

    当前会清理以下几类缓存：
    - gateway:models:all：聚合后的模型列表缓存；
    - metrics:overview:*：仪表盘指标概览缓存（summary/providers/timeseries）；
    - metrics:user-overview:*：用户维度概览缓存；
    - llm:vendor:*:models：各 Provider 的模型列表缓存；
    - llm:logical:*：逻辑模型在 Redis 中的派生表示；
    - llm:metrics:* / llm:metrics:history:*：路由指标缓存与历史窗口。
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以清理缓存",
        )

    if redis is object:
        # 在缺少 Redis 依赖或未配置时，直接返回错误提示。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis 未配置，无法清理缓存",
        )

    segment_patterns: dict[CacheSegment, list[str]] = {
        CacheSegment.MODELS: ["gateway:models:all"],
        CacheSegment.METRICS_OVERVIEW: ["metrics:overview:*"],
        CacheSegment.USER_METRICS_OVERVIEW: ["metrics:user-overview:*"],
        CacheSegment.PROVIDER_MODELS: ["llm:vendor:*:models"],
        CacheSegment.LOGICAL_MODELS: ["llm:logical:*"],
        CacheSegment.ROUTING_METRICS: ["llm:metrics:*", "llm:metrics:history:*"],
    }

    # 若未指定 segments，则默认清理所有分组。
    segments = payload.segments or list(segment_patterns.keys())

    patterns: list[str] = []
    for segment in segments:
        patterns.extend(segment_patterns.get(segment, []))

    stats: dict[str, int] = {}
    total = 0

    for pattern in patterns:
        try:
            removed = await _delete_pattern(redis, pattern)
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception("Failed to clear cache pattern=%s", pattern)
            removed = 0
        stats[pattern] = removed
        total += removed

    logger.info(
        "System cache cleared by user=%s (%s), total_keys=%d, details=%s",
        current_user.username,
        current_user.id,
        total,
        stats,
    )

    return CacheClearResponse(cleared_keys=total, patterns=stats)


@router.put("/provider-limits", response_model=ProviderLimitsResponse)
def update_provider_limits(
    payload: ProviderLimitsUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProviderLimitsResponse:
    """
    更新系统中的 Provider 限制配置（仅当前进程内生效）。
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以更新提供商限制配置",
        )

    # 简单的范围校验：默认上限不能超过最大上限
    if payload.default_user_private_provider_limit > payload.max_user_private_provider_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="默认私有提供商数量上限不能大于最大可配置上限",
        )

    # 直接更新 settings 实例；重启进程后会回到 env 配置
    settings.default_user_private_provider_limit = (
        payload.default_user_private_provider_limit
    )
    settings.max_user_private_provider_limit = payload.max_user_private_provider_limit
    settings.require_approval_for_shared_providers = (
        payload.require_approval_for_shared_providers
    )

    return ProviderLimitsResponse(
        default_user_private_provider_limit=settings.default_user_private_provider_limit,
        max_user_private_provider_limit=settings.max_user_private_provider_limit,
        require_approval_for_shared_providers=settings.require_approval_for_shared_providers,
    )


@router.get("/status")
def get_system_status(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict:
    """
    获取系统状态
    
    Args:
        current_user: 当前认证用户
        
    Returns:
        系统状态信息
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以查看系统状态",
        )

    # 这里可以添加更多的系统状态检查
    status_info = {
        "status": "healthy",
        "message": "系统运行正常",
    }

    return status_info


__all__ = ["router"]
