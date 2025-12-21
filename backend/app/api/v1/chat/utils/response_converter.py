"""
响应格式转换工具：Gemini/Claude -> OpenAI 格式
"""

import time
from typing import Any

from app.logging_config import logger


def convert_claude_response(
    claude_response: dict[str, Any],
    original_model: str,
) -> dict[str, Any]:
    """
    将 Claude API 响应转换为 OpenAI 格式
    
    Args:
        claude_response: Claude API 响应
        original_model: 原始模型名称
    
    Returns:
        OpenAI 格式的响应
    """
    # 如果已经是 OpenAI 格式，直接返回
    if "choices" in claude_response:
        logger.debug("Response already in OpenAI format, skipping transformation")
        return claude_response

    logger.info(
        "Transforming Claude response to OpenAI format response_id=%s stop_reason=%s",
        claude_response.get("id", "unknown"),
        claude_response.get("stop_reason", "unknown"),
    )

    # 转换为 OpenAI 格式
    openai_response = {
        "id": claude_response.get("id", ""),
        "object": "chat.completion",
        "created": int(claude_response.get("created_at", 0)),
        "model": original_model,
        "choices": [],
        "usage": {}
    }

    # 转换 content
    if "content" in claude_response:
        content_blocks = claude_response["content"]
        text_parts = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        openai_response["choices"] = [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "".join(text_parts)
                },
                "finish_reason": claude_response.get("stop_reason", "stop")
            }
        ]

    # 转换 usage
    if "usage" in claude_response:
        usage = claude_response["usage"]
        openai_response["usage"] = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        }

    return openai_response


def convert_gemini_usage(source: dict[str, Any]) -> dict[str, Any]:
    """
    将 Gemini usage 转换为 OpenAI 格式
    
    Args:
        source: Gemini 响应
    
    Returns:
        OpenAI 格式的 usage
    """
    usage = source.get("usageMetadata") or {}
    if not isinstance(usage, dict):
        return {}

    mapped = {
        "prompt_tokens": usage.get("promptTokenCount") or usage.get("promptTokens"),
        "completion_tokens": usage.get("candidatesTokenCount") or usage.get("completionTokens"),
        "total_tokens": usage.get("totalTokenCount") or usage.get("totalTokens"),
    }
    return {k: v for k, v in mapped.items() if v is not None}


def convert_gemini_content_to_segments(content: Any) -> list[dict[str, Any]]:
    """
    将 Gemini content 转换为 segments
    
    Args:
        content: Gemini content
    
    Returns:
        segments 列表
    """
    if not isinstance(content, dict):
        return []

    parts = content.get("parts") or []
    if not isinstance(parts, list):
        return []

    segments = []
    for part in parts:
        if not isinstance(part, dict):
            continue

        if "text" in part:
            segments.append({"type": "text", "text": part["text"]})
        elif "inlineData" in part:
            inline = part["inlineData"]
            if isinstance(inline, dict):
                segments.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{inline.get('mimeType', 'image/jpeg')};base64,{inline.get('data', '')}"
                    }
                })

    return segments


def segments_to_plain_text(segments: list[dict[str, Any]]) -> str:
    """
    将 segments 转换为纯文本
    
    Args:
        segments: segments 列表
    
    Returns:
        纯文本字符串
    """
    text_parts = []
    for seg in segments:
        if seg.get("type") == "text":
            text_parts.append(seg.get("text", ""))
    return "".join(text_parts)


def convert_gemini_response(
    gemini_response: dict[str, Any],
    original_model: str,
) -> dict[str, Any]:
    """
    将 Gemini API 响应转换为 OpenAI 格式
    
    Args:
        gemini_response: Gemini API 响应
        original_model: 原始模型名称
    
    Returns:
        OpenAI 格式的响应
    """
    # 如果已经是 OpenAI 格式，直接返回
    if "choices" in gemini_response:
        logger.debug("Response already in OpenAI format, skipping transformation")
        return gemini_response

    logger.info(
        "Transforming Gemini response to OpenAI format response_id=%s",
        gemini_response.get("id", "unknown"),
    )

    response_id = gemini_response.get("id", f"chatcmpl-{int(time.time())}")
    created_ts = int(time.time())

    create_time = gemini_response.get("createTime") or gemini_response.get("created")
    if isinstance(create_time, (int, float)):
        created_ts = int(create_time)

    choices: list[dict[str, Any]] = []
    candidates = gemini_response.get("candidates") or []

    if isinstance(candidates, list):
        for idx, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                continue

            content = cand.get("content")
            segments = convert_gemini_content_to_segments(content)

            # 检查是否有非文本内容
            has_non_text = any(seg.get("type") != "text" for seg in segments)
            if has_non_text and segments:
                message_content: Any = segments
            else:
                message_content = segments_to_plain_text(segments)

            finish_reason = cand.get("finishReason")
            if isinstance(finish_reason, str):
                finish_reason = finish_reason.lower()

            choices.append({
                "index": idx,
                "message": {
                    "role": "assistant",
                    "content": message_content
                },
                "finish_reason": finish_reason or "stop",
            })

    return {
        "id": response_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": original_model,
        "choices": choices,
        "usage": convert_gemini_usage(gemini_response),
    }
