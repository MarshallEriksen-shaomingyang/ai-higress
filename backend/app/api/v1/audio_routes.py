from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_db, get_http_client, get_redis
from app.schemas.audio import SpeechRequest
from app.services.stt_app_service import STTAppService
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


@router.post(
    "/v1/audio/transcriptions",
    status_code=status.HTTP_200_OK,
    summary="Create transcription (STT)",
    description="OpenAI-compatible speech-to-text endpoint (aggregated gateway).",
)
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    client: Any = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    # 说明：与 OpenAI `audio/transcriptions` 一致，使用 multipart/form-data 上传音频并返回文本。
    try:
        raw = await file.read()
    finally:
        try:
            await file.close()
        except Exception:
            pass

    service = STTAppService(client=client, redis=redis, db=db, api_key=current_key)
    out = await service.transcribe_bytes(
        model=model,
        audio_bytes=raw,
        filename=file.filename or "audio.wav",
        content_type=str(file.content_type or "application/octet-stream"),
        language=language,
        prompt=prompt,
    )
    return {"text": out.text}


__all__ = ["router"]
