"""
上游错误分类（v2）

目标：
- 将“请求本身无效”与“某个 Provider/模型不支持某能力（tools/vision 等）”区分开。
- 对后者：在网关侧视为“可换 provider 重试”，且不应对该 provider 做降权/失败冷却惩罚。
"""

from __future__ import annotations

import json
from typing import Any

_UNSUPPORTED_MARKERS = (
    "does not support",
    "do not support",
    "not support",
    "unsupported",
    "not enabled",
    "not available",
)


_TOOLS_HINTS = (
    "tool",
    "tools",
    "tool_calls",
    "function",
    "functions",
    "function calling",
)


_VISION_HINTS = (
    "vision",
    "image",
    "images",
    "image_url",
    "multimodal",
)


def _extract_message_from_json(obj: Any) -> str | None:
    if isinstance(obj, dict):
        # OpenAI: {"error": {"message": "...", ...}}
        if isinstance(obj.get("error"), dict):
            msg = obj["error"].get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        # Anthropic style: {"type":"error","error":{"message": "..."}}
        msg = obj.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
        # some providers: {"detail": "..."}
        detail = obj.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return None


def extract_error_message(error_text: str | None) -> str:
    if not error_text:
        return ""
    text = str(error_text)
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    msg = _extract_message_from_json(parsed)
    return msg or text


def classify_capability_mismatch(status_code: int | None, error_text: str | None) -> str | None:
    """
    返回 capability key（tools/vision）或 None。

    只对 400/422 这类“请求语义不被上游接受”的错误做保守识别；
    500/429 这类错误仍应走“上游可重试”逻辑。
    """
    if status_code not in (400, 422):
        return None

    msg = extract_error_message(error_text).lower()
    if not msg:
        return None

    if not any(marker in msg for marker in _UNSUPPORTED_MARKERS):
        return None

    if any(hint in msg for hint in _TOOLS_HINTS):
        return "tools"
    if any(hint in msg for hint in _VISION_HINTS):
        return "vision"
    return None


__all__ = ["classify_capability_mismatch", "extract_error_message"]

