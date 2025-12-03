
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.auth import require_api_key
from app.deps import get_redis
from app.errors import not_found
from app.schemas import LogicalModel, PhysicalModel
from app.storage.redis_service import get_logical_model, list_logical_models

router = APIRouter(
    tags=["logical-models"],
    dependencies=[Depends(require_api_key)],
)


class LogicalModelsResponse(BaseModel):
    models: list[LogicalModel] = Field(default_factory=list)
    total: int


class LogicalModelUpstreamsResponse(BaseModel):
    upstreams: list[PhysicalModel] = Field(default_factory=list)


@router.get("/logical-models", response_model=LogicalModelsResponse)
async def list_logical_models_endpoint(
    redis: Redis = Depends(get_redis),
) -> LogicalModelsResponse:
    """
    Return all logical models currently stored in Redis.
    """
    models = await list_logical_models(redis)
    return LogicalModelsResponse(models=models, total=len(models))


@router.get("/logical-models/{logical_model_id}", response_model=LogicalModel)
async def get_logical_model_endpoint(
    logical_model_id: str,
    redis: Redis = Depends(get_redis),
) -> LogicalModel:
    """
    Return a single logical model by id.
    """
    lm = await get_logical_model(redis, logical_model_id)
    if lm is None:
        raise not_found(f"Logical model '{logical_model_id}' not found")
    return lm


@router.get(
    "/logical-models/{logical_model_id}/upstreams",
    response_model=LogicalModelUpstreamsResponse,
)
async def get_logical_model_upstreams_endpoint(
    logical_model_id: str,
    redis: Redis = Depends(get_redis),
) -> LogicalModelUpstreamsResponse:
    """
    Return the upstream physical models mapped to a logical model.
    """
    lm = await get_logical_model(redis, logical_model_id)
    if lm is None:
        raise not_found(f"Logical model '{logical_model_id}' not found")
    return LogicalModelUpstreamsResponse(upstreams=lm.upstreams)


__all__ = ["router"]

