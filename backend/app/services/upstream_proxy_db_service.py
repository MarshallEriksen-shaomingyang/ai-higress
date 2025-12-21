from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import UpstreamProxyConfig, UpstreamProxyEndpoint, UpstreamProxySource
from app.services.encryption import decrypt_secret, encrypt_secret

from .upstream_proxy_utils import (
    ParsedProxy,
    build_proxy_url,
    compute_identity_hash,
    normalize_scheme,
    safe_json_dumps,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def get_or_create_proxy_config(db: Session) -> UpstreamProxyConfig:
    row = db.execute(select(UpstreamProxyConfig)).scalars().first()
    if row is None:
        row = UpstreamProxyConfig()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


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


def upsert_endpoints(
    db: Session,
    *,
    source: UpstreamProxySource,
    proxies: Iterable[ParsedProxy],
    mark_seen: bool,
) -> int:
    """
    Upsert a batch of proxies under the given source.
    Returns number of endpoints inserted/updated.
    """
    now = utcnow()
    count = 0
    for proxy in proxies:
        scheme = normalize_scheme(proxy.scheme)
        identity_hash = compute_identity_hash(
            scheme=scheme,
            host=proxy.host,
            port=proxy.port,
            username=proxy.username,
        )

        stmt: Select[tuple[UpstreamProxyEndpoint]] = select(UpstreamProxyEndpoint).where(
            UpstreamProxyEndpoint.source_id == source.id,
            UpstreamProxyEndpoint.identity_hash == identity_hash,
        )
        endpoint = db.execute(stmt).scalars().first()
        if endpoint is None:
            endpoint = UpstreamProxyEndpoint(
                source_id=source.id,
                scheme=scheme,
                host=proxy.host,
                port=proxy.port,
                username=proxy.username,
                password_encrypted=encrypt_secret(proxy.password) if proxy.password else None,
                identity_hash=identity_hash,
                enabled=True,
            )
            db.add(endpoint)
            count += 1
        else:
            endpoint.scheme = scheme
            endpoint.host = proxy.host
            endpoint.port = proxy.port
            endpoint.username = proxy.username
            endpoint.password_encrypted = encrypt_secret(proxy.password) if proxy.password else None
            count += 1

        if mark_seen:
            endpoint.last_seen_at = now
    return count


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
    "get_or_create_proxy_config",
    "get_source_remote_headers",
    "get_source_remote_url",
    "set_source_remote_headers",
    "set_source_remote_url",
    "upsert_endpoints",
    "utcnow",
]

