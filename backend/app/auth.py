import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_redis
from app.services.api_key_cache import (
    CachedAPIKey,
    build_cache_entry,
    cache_api_key,
    get_cached_api_key,
    invalidate_cached_api_key,
)
from app.services.api_key_service import derive_api_key_hash, find_api_key_by_hash


@dataclass
class AuthenticatedAPIKey:
    id: UUID
    user_id: UUID
    user_username: str
    is_superuser: bool
    name: str
    is_active: bool
    disabled_reason: str | None
    has_provider_restrictions: bool
    allowed_provider_ids: list[str]


def _decode_token(token: str) -> str:
    """
    Decode base64 token; raise if invalid or unexpected.
    """
    try:
        decoded_bytes = base64.b64decode(token, validate=True)
        decoded = decoded_bytes.decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    return decoded


async def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
) -> AuthenticatedAPIKey:
    """
    Validate client API keys stored in the数据库。

    Preferred：Authorization: Bearer <base64(token)>；兼容 X-API-Key: <base64(token)>。
    Base64 解码后与数据库中的哈希值比对，支持多用户多密钥。
    """
    token_value: str | None = None

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header, expected 'Bearer <token>'",
            )
        token_value = token
    elif x_api_key:
        token_value = x_api_key.strip() or None

    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization or X-API-Key header",
        )

    decoded = _decode_token(token_value)
    key_hash = derive_api_key_hash(decoded)
    cached = await get_cached_api_key(redis, key_hash)
    if cached is not None:
        if cached.expires_at is not None and cached.expires_at <= datetime.now(UTC):
            await invalidate_cached_api_key(redis, key_hash)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API token expired",
            )
        if not cached.is_active:
            await invalidate_cached_api_key(redis, key_hash)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=cached.disabled_reason or "API token disabled",
            )
        if not cached.user_is_active:
            await invalidate_cached_api_key(redis, key_hash)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API token owner is inactive",
            )
        return _cached_to_authenticated(cached)

    api_key = find_api_key_by_hash(db, key_hash)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    if api_key.expires_at is not None and api_key.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token expired",
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=api_key.disabled_reason or "API token disabled",
        )

    if not api_key.user or not api_key.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API token owner is inactive",
        )

    cache_entry = build_cache_entry(api_key)
    await cache_api_key(redis, key_hash, cache_entry)
    return _cached_to_authenticated(cache_entry)


def _cached_to_authenticated(entry: CachedAPIKey) -> AuthenticatedAPIKey:
    return AuthenticatedAPIKey(
        id=UUID(entry.id),
        user_id=UUID(entry.user_id),
        user_username=entry.user_username,
        is_superuser=entry.user_is_superuser,
        name=entry.name,
        is_active=entry.is_active,
        disabled_reason=entry.disabled_reason,
        has_provider_restrictions=entry.has_provider_restrictions,
        allowed_provider_ids=list(entry.allowed_provider_ids),
    )


__all__ = ["AuthenticatedAPIKey", "require_api_key"]
