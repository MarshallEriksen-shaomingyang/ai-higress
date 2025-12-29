"""
公共网关相关的基础路由：
- /health
- /models 与 /v1/models

从 app.routes 中抽离出来，避免 routes.py 过于臃肿。
"""

from fastapi import APIRouter, Depends

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺少 redis 时的兜底类型
    Redis = object  # type: ignore[misc,assignment]

from sqlalchemy.orm import Session

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_db, get_redis
from app.services.chat_routing_service import HealthResponse, ModelsResponse, _get_or_fetch_models

router = APIRouter(tags=["gateway"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """简单健康检查端点。"""

    return HealthResponse()


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
) -> ModelsResponse:
    """
    列出当前 API Key 可访问的模型列表。

    - 无 provider 限制时走全局缓存；
    - 有 provider 限制时只返回允许的 provider 下模型。
    """

    return await _get_or_fetch_models(redis, db, current_key)


@router.get("/v1/models", response_model=ModelsResponse)
async def list_models_v1(
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
) -> ModelsResponse:
    """
    /models 的向后兼容别名，某些 SDK 默认请求 /v1/models。
    """

    return await list_models(redis=redis, db=db, current_key=current_key)


__all__ = ["router"]
