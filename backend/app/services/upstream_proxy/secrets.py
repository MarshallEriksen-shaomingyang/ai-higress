from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.logging_config import logger
from app.models import UpstreamProxyEndpoint, UpstreamProxySource
from app.services.encryption import decrypt_secret, encrypt_secret

from .utils import ParsedProxy, build_proxy_url, safe_json_dumps


def utcnow() -> datetime:
    return datetime.now(UTC)


def encrypt_optional_json(value: dict[str, Any] | None) -> bytes | None:
    if not value:
        return None
    return encrypt_secret(safe_json_dumps(value))


def decrypt_optional_json(token: bytes | str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        plaintext = decrypt_secret(token)
        return json.loads(plaintext)
    except Exception:
        logger.warning("upstream_proxy: failed to decrypt json payload")
        return None


def set_source_remote_url(source: UpstreamProxySource, url: str | None) -> None:
    if url:
        source.remote_url_encrypted = encrypt_secret(url)
    else:
        source.remote_url_encrypted = None


def get_source_remote_url(source: UpstreamProxySource) -> str | None:
    if not source.remote_url_encrypted:
        return None
    return decrypt_secret(source.remote_url_encrypted)


def set_source_remote_headers(source: UpstreamProxySource, headers: dict[str, Any] | None) -> None:
    source.remote_headers_encrypted = encrypt_optional_json(headers)


def get_source_remote_headers(source: UpstreamProxySource) -> dict[str, Any] | None:
    return decrypt_optional_json(source.remote_headers_encrypted)


def build_endpoint_proxy_url(endpoint: UpstreamProxyEndpoint) -> str:
    password = None
    if endpoint.password_encrypted:
        password = decrypt_secret(endpoint.password_encrypted)
    parsed = ParsedProxy(
        scheme=endpoint.scheme,
        host=endpoint.host,
        port=int(endpoint.port),
        username=endpoint.username,
        password=password,
    )
    return build_proxy_url(parsed)


__all__ = [
    "build_endpoint_proxy_url",
    "decrypt_optional_json",
    "encrypt_optional_json",
    "get_source_remote_headers",
    "get_source_remote_url",
    "set_source_remote_headers",
    "set_source_remote_url",
    "utcnow",
]

