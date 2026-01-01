from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response

from app.services.audio_storage_service import (
    AudioStorageNotConfigured,
    SignedAudioUrlError,
    get_effective_audio_storage_mode,
    load_audio_bytes,
    presign_audio_get_url,
    verify_signed_audio_request,
)
from app.services.image_storage_service import (
    ImageStorageNotConfigured,
    SignedUrlError,
    get_effective_image_storage_mode,
    load_image_bytes,
    presign_image_get_url,
    verify_signed_image_request,
)

router = APIRouter(tags=["media"])


@router.get("/media/images/{object_key:path}", include_in_schema=False)
async def get_generated_image(
    object_key: str,
    expires: int = Query(..., description="Unix timestamp (seconds)"),
    sig: str = Query(..., description="HMAC signature"),
):
    """
    通过“网关短链签名”访问文生图结果图片。

    说明：
    - 不要求 API Key/JWT 鉴权；
    - 通过 expires+sig 做短链校验；
    - 图片可存储在本地磁盘或 OSS/S3；
      - 本地模式：网关校验签名后直接返回图片二进制；
      - OSS/S3 模式：网关校验签名后 302 跳转到对象存储预签名 URL（直下）。
    """
    try:
        verify_signed_image_request(object_key, expires=expires, sig=sig)
    except SignedUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    if get_effective_image_storage_mode() == "local":
        try:
            body, content_type = await load_image_bytes(object_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found") from exc
        return Response(content=body, media_type=content_type, headers={"Cache-Control": "no-store"})

    try:
        remaining = max(1, int(expires) - int(time.time()))
        url = await presign_image_get_url(object_key, expires_seconds=remaining)
    except ImageStorageNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found") from exc

    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})


@router.get("/media/audio/{object_key:path}", include_in_schema=False)
async def get_user_audio(
    object_key: str,
    expires: int = Query(..., description="Unix timestamp (seconds)"),
    sig: str = Query(..., description="HMAC signature"),
):
    """
    通过“网关短链签名”访问用户上传的音频（语音输入）。

    说明：
    - 不要求 API Key/JWT 鉴权；
    - 通过 expires+sig 做短链校验；
    - 音频可存储在本地磁盘或 OSS/S3；
      - 本地模式：网关校验签名后直接返回音频二进制；
      - OSS/S3 模式：网关校验签名后 302 跳转到对象存储预签名 URL（直下）。
    """
    try:
        verify_signed_audio_request(object_key, expires=expires, sig=sig)
    except SignedAudioUrlError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if get_effective_audio_storage_mode() == "local":
        try:
            body, content_type = await load_audio_bytes(object_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audio not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audio not found") from exc
        return Response(content=body, media_type=content_type, headers={"Cache-Control": "no-store"})

    try:
        remaining = max(1, int(expires) - int(time.time()))
        url = await presign_audio_get_url(object_key, expires_seconds=remaining)
    except AudioStorageNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audio not found") from exc

    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})


__all__ = ["router"]
