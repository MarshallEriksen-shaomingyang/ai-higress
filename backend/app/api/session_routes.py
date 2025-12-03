from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.auth import require_api_key
from app.deps import get_redis
from app.errors import not_found
from app.schemas import Session
from app.routing.session_manager import delete_session, get_session

router = APIRouter(
    tags=["sessions"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/routing/sessions/{conversation_id}", response_model=Session)
async def get_session_endpoint(
    conversation_id: str,
    redis: Redis = Depends(get_redis),
) -> Session:
    """
    Return session information for a conversation.
    """
    sess = await get_session(redis, conversation_id)
    if sess is None:
        raise not_found(f"Session '{conversation_id}' not found")
    return sess


@router.delete(
    "/routing/sessions/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session_endpoint(
    conversation_id: str,
    redis: Redis = Depends(get_redis),
) -> Response:
    """
    Delete a conversation session (cancel stickiness).
    """
    existed = await delete_session(redis, conversation_id)
    if not existed:
        raise not_found(f"Session '{conversation_id}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]

