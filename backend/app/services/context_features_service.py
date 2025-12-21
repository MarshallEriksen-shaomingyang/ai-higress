from __future__ import annotations

import re
from typing import Any

from app.services.bandit_policy_service import infer_language, length_bucket

_CODE_FENCE_RE = re.compile(r"```")
_CODE_LIKE_RE = re.compile(
    r"(^|\n)\s*(def |class |import |from |return |async |await |try:|except |raise |if __name__|#include|SELECT |INSERT |UPDATE |DELETE )",
    re.IGNORECASE,
)

_TRANSLATION_HINT_RE = re.compile(r"\btranslate\b|翻译|译成|翻成", re.IGNORECASE)
_WRITING_HINT_RE = re.compile(
    r"写一篇|写个|写封|写一封|文章|博客|文案|润色|改写|扩写|缩写|总结|概括|\brewrite\b|\bpolish\b|\bsummarize\b",
    re.IGNORECASE,
)
_QA_HINT_RE = re.compile(r"[?？]|怎么|为什么|如何|怎样|是什么|\bhow\b|\bwhy\b|\bwhat\b", re.IGNORECASE)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CN_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
_CN_ID_RE = re.compile(r"\b\d{17}[\dXx]\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def detect_tool_mode(payload: dict[str, Any] | None) -> str:
    """
    低基数识别：none / tools / functions
    - tools: OpenAI tool calling（tools/tool_choice/tool_calls）
    - functions: 旧版 functions/function_call
    """
    if not isinstance(payload, dict):
        return "none"

    tools = payload.get("tools")
    if isinstance(tools, list) and tools:
        return "tools"
    if payload.get("tool_choice") is not None:
        return "tools"

    functions = payload.get("functions")
    if isinstance(functions, list) and functions:
        return "functions"
    if payload.get("function_call") is not None:
        return "functions"

    messages = payload.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "tool":
                return "tools"
            if msg.get("tool_calls") is not None:
                return "tools"
            if msg.get("function_call") is not None:
                return "functions"

    return "none"


def classify_task_type(user_text: str) -> str:
    """
    低基数 task_type：
    - code / translation / writing / qa / unknown
    """
    text = (user_text or "").strip()
    if not text:
        return "unknown"

    if _TRANSLATION_HINT_RE.search(text):
        return "translation"
    if _CODE_FENCE_RE.search(text) or _CODE_LIKE_RE.search(text):
        return "code"
    if _WRITING_HINT_RE.search(text):
        return "writing"
    if _QA_HINT_RE.search(text):
        return "qa"
    return "unknown"


def classify_risk_tier(user_text: str) -> str:
    """
    风险/合规离散化：low / medium / high
    - high: 身份证/卡号等高敏
    - medium: 邮箱/手机号等 PII
    - low: 未发现明显 PII
    """
    text = user_text or ""
    if not text:
        return "low"

    if _CN_ID_RE.search(text):
        return "high"

    # 卡号判定可能误伤，保守一点：同时包含空格/连字符 或长度较长才算 high
    m = _CARD_RE.search(text)
    if m:
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 16 and ((" " in raw) or ("-" in raw)):
            return "high"

    if _EMAIL_RE.search(text) or _CN_PHONE_RE.search(text):
        return "medium"

    return "low"


def build_rule_context_features(
    *,
    user_text: str,
    request_payload: dict[str, Any] | None,
) -> dict[str, str]:
    tool_mode = detect_tool_mode(request_payload)
    task_type = classify_task_type(user_text)
    risk_tier = classify_risk_tier(user_text)
    return {
        "language": infer_language(user_text),
        "length_bucket": length_bucket(user_text),
        "tool_mode": tool_mode,
        "task_type": task_type,
        "risk_tier": risk_tier,
    }


__all__ = [
    "build_rule_context_features",
    "classify_risk_tier",
    "classify_task_type",
    "detect_tool_mode",
]

