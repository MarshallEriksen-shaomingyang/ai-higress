from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_db, get_http_client, get_redis
from app.schemas.audio import SpeechRequest
from app.services.tts_app_service import TTSAppService, _content_type_for_format

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


router = APIRouter(tags=["audio"])


@router.post(
    "/v1/audio/speech",
    status_code=status.HTTP_200_OK,
    summary="Create speech (TTS)",
    description="OpenAI-compatible text-to-speech endpoint (aggregated gateway).",
)
async def create_speech(
    request: SpeechRequest = Body(...),
    client: Any = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    try:
        service = TTSAppService(client=client, redis=redis, db=db, api_key=current_key)
        audio_bytes = await service.generate_speech_bytes(request)
        return Response(
            content=audio_bytes,
            media_type=_content_type_for_format(request.response_format),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "TTS 服务异常"},
        ) from exc


__all__ = ["router"]
