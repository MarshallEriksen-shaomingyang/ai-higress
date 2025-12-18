from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlparse

_WHITESPACE_RE = re.compile(r"\s+")


def _collapse_spaces(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _safe_truncate(value: str, *, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[:max_len].rstrip()


def _host_from_url(value: str) -> str | None:
    try:
        parsed = urlparse(value)
    except Exception:
        return None
    host = (parsed.hostname or "").strip()
    return host or None


def infer_client_app_name(headers: Mapping[str, str]) -> str:
    """
    从客户端请求头中推断“应用/客户端”名称（用于指标聚合）。

    优先级（从高到低）：
    1) X-Title（很多桌面客户端会携带）
    2) User-Agent 第一个 product token（例如 RooCode/3.36.12 -> RooCode）
    3) Referer/Origin 的 hostname（例如 https://cherry-ai.com -> cherry-ai.com）
    4) unknown

    注意：该值可被客户端伪造，因此这里做了长度限制与空白规整，以降低高基数风险。
    """
    raw_title = headers.get("x-title", "") or ""
    raw_title = _collapse_spaces(raw_title)
    if raw_title:
        return _safe_truncate(raw_title, max_len=80)

    user_agent = _collapse_spaces(headers.get("user-agent", "") or "")
    if user_agent:
        token = user_agent.split(" ", 1)[0].strip()
        if token:
            name = token.split("/", 1)[0].strip()
            # 绝大多数浏览器 UA 都以 Mozilla/... 开头，不适合作为“应用”聚合键。
            if name and name.lower() not in {"mozilla", "mozilla/5.0"}:
                return _safe_truncate(name, max_len=80)

    referer = headers.get("http-referer") or headers.get("referer") or ""
    origin = headers.get("origin") or ""
    host = _host_from_url(referer) or _host_from_url(origin)
    if host:
        return _safe_truncate(host, max_len=80)

    return "unknown"


__all__ = ["infer_client_app_name"]

