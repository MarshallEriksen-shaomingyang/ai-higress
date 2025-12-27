from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.services.image_storage_service import (
    ImageStorageNotConfigured,
    SignedUrlError,
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
    - 图片实际存储在 OSS 私有桶中，网关校验签名后 302 跳转到 OSS 预签名 URL（直下）。
    """
    try:
        verify_signed_image_request(object_key, expires=expires, sig=sig)
    except SignedUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        remaining = max(1, int(expires) - int(time.time()))
        url = await presign_image_get_url(object_key, expires_seconds=remaining)
    except ImageStorageNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found") from exc

    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})


__all__ = ["router"]
