import base64

from fastapi import Header, HTTPException, status

from service.settings import settings


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

    expected = settings.api_auth_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway token is not configured",
        )

    if decoded != expected:
        # Only accept the literal configured value after decoding.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    return decoded


async def require_api_key(authorization: str | None = Header(default=None)) -> str:
    """
    Simple API key guard.

    Expects header: Authorization: Bearer <base64(token)>
    After base64 解码结果必须与 APIPROXY_AUTH_TOKEN 的值一致，否则返回 401。
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header, expected 'Bearer <token>'",
        )

    return _decode_token(token)
