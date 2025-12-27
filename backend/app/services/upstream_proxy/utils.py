from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

from app.settings import settings

VALID_PROXY_SCHEMES = {"http", "https", "socks5", "socks5h"}


@dataclass(frozen=True, slots=True)
class ParsedProxy:
    scheme: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None


def normalize_scheme(value: str) -> str:
    scheme = (value or "").strip().lower()
    if scheme not in VALID_PROXY_SCHEMES:
        raise ValueError(f"Unsupported proxy scheme: {value!r}")
    return scheme


def compute_identity_hash(
    *,
    scheme: str,
    host: str,
    port: int,
    username: str | None,
) -> str:
    """
    Stable HMAC identifier for de-duplication.

    We avoid using encrypted fields in unique constraints; instead we compute a
    deterministic identity from non-sensitive fields + username (if any).
    """
    msg = f"{scheme}://{host}:{port}|{username or ''}".encode()
    secret = settings.secret_key.encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def compute_url_fingerprint(proxy_url: str) -> str:
    """
    Fingerprint used to map a runtime proxy_url back to endpoint_id via Redis.

    This allows request-side failure reporting without changing the existing
    pick_upstream_proxy() return type.
    """
    msg = proxy_url.encode("utf-8")
    secret = settings.secret_key.encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def build_proxy_url(parsed: ParsedProxy) -> str:
    """
    Build an httpx-compatible proxy URL string.
    """
    scheme = normalize_scheme(parsed.scheme)
    auth = ""
    if parsed.username:
        user = quote(parsed.username, safe="")
        if parsed.password is not None:
            pwd = quote(parsed.password, safe="")
            auth = f"{user}:{pwd}@"
        else:
            auth = f"{user}@"
    return f"{scheme}://{auth}{parsed.host}:{parsed.port}"


def mask_proxy_url(proxy_url: str) -> str:
    """
    Mask credentials in logs while keeping scheme/host/port visible.
    """
    try:
        parsed = urlparse(proxy_url)
        if not parsed.scheme or not parsed.hostname or parsed.port is None:
            return proxy_url
        auth = ""
        if parsed.username:
            auth = f"{parsed.username}:***@"
        return f"{parsed.scheme}://{auth}{parsed.hostname}:{parsed.port}"
    except Exception:
        return proxy_url


_LINE_SPLIT_RE = re.compile(r"[,\n;]+")


def split_proxy_text(raw: str) -> list[str]:
    if not raw:
        return []
    return [s.strip() for s in _LINE_SPLIT_RE.split(raw) if s.strip()]


def parse_proxy_line(line: str, *, default_scheme: str) -> ParsedProxy:
    """
    Parse a single proxy line.

    Supported formats:
    - Full URL:  http(s)://user:pass@host:port  /  socks5(h)://host:port
    - host:port
    - host:port:username:password  (e.g. Webshare download format)
    """
    s = (line or "").strip()
    if not s:
        raise ValueError("Empty proxy line")

    if "://" in s:
        parsed = urlparse(s)
        if not parsed.scheme or not parsed.hostname or parsed.port is None:
            raise ValueError(f"Invalid proxy URL: {s!r}")
        scheme = normalize_scheme(parsed.scheme)
        return ParsedProxy(
            scheme=scheme,
            host=parsed.hostname,
            port=int(parsed.port),
            username=parsed.username,
            password=parsed.password,
        )

    parts = s.split(":")
    if len(parts) == 2:
        host, port_s = parts
        return ParsedProxy(
            scheme=normalize_scheme(default_scheme),
            host=host,
            port=int(port_s),
        )
    if len(parts) == 4:
        host, port_s, username, password = parts
        return ParsedProxy(
            scheme=normalize_scheme(default_scheme),
            host=host,
            port=int(port_s),
            username=username or None,
            password=password or None,
        )
    raise ValueError(f"Unsupported proxy line format: {s!r}")


def safe_json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


__all__ = [
    "VALID_PROXY_SCHEMES",
    "ParsedProxy",
    "build_proxy_url",
    "compute_identity_hash",
    "compute_url_fingerprint",
    "mask_proxy_url",
    "normalize_scheme",
    "parse_proxy_line",
    "safe_json_dumps",
    "split_proxy_text",
]
