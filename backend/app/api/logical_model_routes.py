
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_db, get_redis
from app.errors import not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.schemas import (
    LogicalModel,
    LogicalModelUpstreamsResponse,
    LogicalModelsResponse,
    PhysicalModel,
)
from app.services.user_provider_service import get_accessible_provider_ids
from app.storage.redis_service import get_logical_model, list_logical_models

router = APIRouter(
    tags=["logical-models"],
    dependencies=[Depends(require_jwt_token)],
)


@router.get("/logical-models", response_model=LogicalModelsResponse)
async def list_logical_models_endpoint(
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> LogicalModelsResponse:
    """
    返回当前用户可访问的逻辑模型，使用 Cache-Aside 模式：
    1. 优先从 Redis 读取全量逻辑模型
    2. 缓存未命中时从数据库回源并写入缓存
    3. 根据用户权限过滤结果
    """
    # 尝试从 Redis 读取
    models = await list_logical_models(redis)
    
    # 缓存未命中，从数据库回源
    if not models:
        logger.info("Logical models cache miss, falling back to database")
        from app.services.logical_model_sync import sync_logical_models
        
        try:
            # 从数据库聚合并写入 Redis
            models = await sync_logical_models(redis, session=db)
            logger.info("Synced %d logical models from database to Redis", len(models))
        except Exception:
            logger.exception("Failed to sync logical models from database")
            # 即使同步失败，也返回空列表而不是报错
            models = []
    
    # 根据用户权限过滤逻辑模型
    accessible_provider_ids = get_accessible_provider_ids(db, UUID(current_user.id))
    
    filtered_models: list[LogicalModel] = []
    for model in models:
        # 过滤出用户可访问的上游
        accessible_upstreams = [
            upstream for upstream in model.upstreams
            if upstream.provider_id in accessible_provider_ids
        ]
        
        # 如果该逻辑模型至少有一个可访问的上游，则包含它
        if accessible_upstreams:
            filtered_models.append(
                model.model_copy(update={"upstreams": accessible_upstreams})
            )
    
    return LogicalModelsResponse(models=filtered_models, total=len(filtered_models))


@router.get("/logical-models/{logical_model_id}", response_model=LogicalModel)
async def get_logical_model_endpoint(
    logical_model_id: str,
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> LogicalModel:
    """
    返回单个逻辑模型（仅包含用户可访问的上游），使用 Cache-Aside 模式：
    1. 优先从 Redis 读取
    2. 缓存未命中时从数据库回源
    3. 根据用户权限过滤上游列表
    """
    # 尝试从 Redis 读取
    lm = await get_logical_model(redis, logical_model_id)
    
    # 缓存未命中，从数据库回源
    if lm is None:
        logger.info("Logical model '%s' cache miss, falling back to database", logical_model_id)
        from app.services.logical_model_sync import sync_logical_models
        
        try:
            # 从数据库聚合并写入 Redis
            models = await sync_logical_models(redis, session=db)
            # 再次尝试读取
            lm = await get_logical_model(redis, logical_model_id)
        except Exception:
            logger.exception("Failed to sync logical models from database")
    
    if lm is None:
        raise not_found(f"Logical model '{logical_model_id}' not found")
    
    # 根据用户权限过滤上游
    accessible_provider_ids = get_accessible_provider_ids(db, UUID(current_user.id))
    accessible_upstreams = [
        upstream for upstream in lm.upstreams
        if upstream.provider_id in accessible_provider_ids
    ]
    
    # 如果用户没有任何可访问的上游，返回 404
    if not accessible_upstreams:
        raise not_found(f"Logical model '{logical_model_id}' not found or not accessible")
    
    return lm.model_copy(update={"upstreams": accessible_upstreams})


@router.get(
    "/logical-models/{logical_model_id}/upstreams",
    response_model=LogicalModelUpstreamsResponse,
)
async def get_logical_model_upstreams_endpoint(
    logical_model_id: str,
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> LogicalModelUpstreamsResponse:
    """
    返回逻辑模型的上游物理模型列表（仅包含用户可访问的上游），使用 Cache-Aside 模式。
    """
    # 尝试从 Redis 读取
    lm = await get_logical_model(redis, logical_model_id)
    
    # 缓存未命中，从数据库回源
    if lm is None:
        logger.info("Logical model '%s' cache miss for upstreams, falling back to database", logical_model_id)
        from app.services.logical_model_sync import sync_logical_models
        
        try:
            # 从数据库聚合并写入 Redis
            await sync_logical_models(redis, session=db)
            # 再次尝试读取
            lm = await get_logical_model(redis, logical_model_id)
        except Exception:
            logger.exception("Failed to sync logical models from database")
    
    if lm is None:
        raise not_found(f"Logical model '{logical_model_id}' not found")
    
    # 根据用户权限过滤上游
    accessible_provider_ids = get_accessible_provider_ids(db, UUID(current_user.id))
    accessible_upstreams = [
        upstream for upstream in lm.upstreams
        if upstream.provider_id in accessible_provider_ids
    ]
    
    # 如果用户没有任何可访问的上游，返回 404
    if not accessible_upstreams:
        raise not_found(f"Logical model '{logical_model_id}' not found or not accessible")
    
    return LogicalModelUpstreamsResponse(upstreams=accessible_upstreams)


__all__ = ["router"]
