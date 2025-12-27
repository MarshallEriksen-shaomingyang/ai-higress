from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import UpstreamProxyConfig, UpstreamProxyEndpoint, UpstreamProxySource
from app.services.encryption import encrypt_secret
from app.services.upstream_proxy.utils import ParsedProxy, compute_identity_hash, normalize_scheme


def get_or_create_proxy_config(db: Session) -> UpstreamProxyConfig:
    row = db.execute(select(UpstreamProxyConfig)).scalars().first()
    if row is None:
        row = UpstreamProxyConfig()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


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
    now = datetime.now(UTC)
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


__all__ = [
    "get_or_create_proxy_config",
    "upsert_endpoints",
]

