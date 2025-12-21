import copy
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass
class ContentFinding:
    """检测到的敏感片段。"""

    category: str
    snippet: str


@dataclass
class ContentCheckResult:
    redacted: Any
    findings: list[ContentFinding]
    blocked: bool


_SECRET_PATTERNS: dict[str, Iterable[re.Pattern[str]]] = {
    "secret": [
        re.compile(r"sk-[A-Za-z0-9]{16,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"AIza[0-9A-Za-z_-]{35}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ],
    "pii": [
        re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
        re.compile(r"\b1[3-9]\d{9}\b"),  # 简单手机号
    ],
    "code": [
        re.compile(r"(?i)password\s*[:=]\s*['\"]?[A-Za-z0-9_@!#$%^&*-]{6,}"),
        re.compile(r"(?i)secret\s*[:=]\s*['\"]?[A-Za-z0-9_@!#$%^&*-]{6,}"),
    ],
}


def _compact_snippet(snippet: str, max_len: int = 80) -> str:
    snippet = snippet.strip()
    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len // 2] + "..." + snippet[-max_len // 2 :]


def _scan_text(text: str, findings: list[ContentFinding]) -> None:
    for category, patterns in _SECRET_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                findings.append(
                    ContentFinding(category=category, snippet=_compact_snippet(match.group(0)))
                )


def _redact_text(text: str, mask_token: str) -> str:
    redacted = text
    for patterns in _SECRET_PATTERNS.values():
        for pattern in patterns:
            redacted = pattern.sub(mask_token, redacted)
    return redacted


def _walk_and_redact(value: Any, *, findings: list[ContentFinding], mask_token: str | None) -> Any:
    if isinstance(value, str):
        _scan_text(value, findings)
        if mask_token:
            return _redact_text(value, mask_token)
        return value

    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore")
        _scan_text(text, findings)
        if mask_token:
            return _redact_text(text, mask_token).encode("utf-8")
        return value

    if isinstance(value, list):
        return [
            _walk_and_redact(item, findings=findings, mask_token=mask_token) for item in value
        ]

    if isinstance(value, dict):
        return {
            k: _walk_and_redact(v, findings=findings, mask_token=mask_token)
            for k, v in value.items()
        }

    # Primitive or unsupported types are returned as-is.
    return value


def apply_content_policy(
    value: Any,
    *,
    action: str,
    mask_token: str,
    mask_output: bool = False,
) -> ContentCheckResult:
    """
    对任意结构内容做敏感信息检测与可选打码。

    - action=log: 仅记录 findings，不修改内容。
    - action=mask: 记录 findings，并在 mask_output=True 时返回打码后的内容。
    - action=block: 记录 findings，若命中则 blocked=True。
    """
    findings: list[ContentFinding] = []
    redacted_source = copy.deepcopy(value) if mask_output else value
    redacted = _walk_and_redact(
        redacted_source,
        findings=findings,
        mask_token=mask_token if mask_output else None,
    )
    blocked = bool(findings) and action == "block"
    return ContentCheckResult(redacted=redacted, findings=findings, blocked=blocked)


def redact_for_storage(value: Any, mask_token: str) -> Any:
    """永远对存储副本做打码，防止在上下文/日志中泄漏敏感信息。"""
    findings: list[ContentFinding] = []
    return _walk_and_redact(copy.deepcopy(value), findings=findings, mask_token=mask_token)


def findings_to_summary(findings: Iterable[ContentFinding]) -> list[str]:
    """将检测结果转成便于返回/日志的短摘要。"""
    return [f"{item.category}: {item.snippet}" for item in findings]
