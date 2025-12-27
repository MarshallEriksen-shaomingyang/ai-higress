from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.schemas.image import ImageGenerationRequest, ImageGenerationResponse
from app.services.image_app_service import ImageAppService
from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_db, get_http_client, get_redis

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from sqlalchemy.orm import Session

router = APIRouter(tags=["images"])

@router.post(
    "/v1/images/generations",
    response_model=ImageGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate images from text",
    description="Creates an image given a prompt.",
)
async def generate_image(
    request: ImageGenerationRequest = Body(...),
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    OpenAI-compatible image generation endpoint.
    """
    try:
        service = ImageAppService(client=client, redis=redis, db=db, api_key=current_key)
        return await service.generate_image(request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
