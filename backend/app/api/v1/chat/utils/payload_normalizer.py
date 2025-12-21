"""
Payload 标准化工具：检测 API 风格、标准化请求参数
"""

from typing import Any


def detect_api_style(payload: dict[str, Any]) -> str:
    """
    检测请求 payload 的 API 风格（OpenAI / Claude / Gemini）
    
    Args:
        payload: 请求 payload
    
    Returns:
        str: "openai" | "claude" | "gemini"
    """
    # Claude 风格：使用 max_tokens_to_sample 或 anthropic_version
    if "max_tokens_to_sample" in payload:
        return "claude"
    if "anthropic_version" in payload:
        return "claude"

    # Gemini 风格：使用 contents 而不是 messages
    if "contents" in payload and "messages" not in payload:
        return "gemini"

    # OpenAI 新 API 使用 max_completion_tokens
    if "max_completion_tokens" in payload and "anthropic_version" not in payload:
        return "openai"

    # 默认：OpenAI 风格
    return "openai"


def normalize_payload(
    payload: dict[str, Any],
    *,
    provider_model_id: str,
    api_style: str | None = None,
) -> dict[str, Any]:
    """
    标准化请求 payload，替换模型名称
    
    Args:
        payload: 原始请求 payload
        provider_model_id: Provider 的模型 ID
        api_style: API 风格（如果为 None 则自动检测）
    
    Returns:
        dict: 标准化后的 payload（新字典，不修改原始 payload）
    """
    if api_style is None:
        api_style = detect_api_style(payload)

    # 创建副本
    normalized = dict(payload)

    # 替换模型名称
    normalized["model"] = provider_model_id

    return normalized


def extract_model_name(payload: dict[str, Any]) -> str | None:
    """
    从 payload 中提取模型名称
    
    Args:
        payload: 请求 payload
    
    Returns:
        str | None: 模型名称，如果不存在则返回 None
    """
    return payload.get("model")


def is_streaming_request(payload: dict[str, Any]) -> bool:
    """
    判断是否为流式请求
    
    Args:
        payload: 请求 payload
    
    Returns:
        bool: 是否为流式请求
    """
    return payload.get("stream", False) is True
