from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.services.image_storage_service import (
    ImageStorageNotConfigured,
    SignedUrlError,
    load_image_bytes,
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
    - 图片实际存储在 OSS 私有桶中，由后端代为读取并返回。
    """
    try:
        verify_signed_image_request(object_key, expires=expires, sig=sig)
    except SignedUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        body, content_type = await load_image_bytes(object_key)
    except ImageStorageNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found") from exc

    return Response(content=body, media_type=content_type)


__all__ = ["router"]

