"""
Claude Code CLI Request/Response Transformer

This module provides functions to transform requests and responses between
OpenAI format and Claude Code CLI format, including user_id generation and
header construction.
"""

import hashlib
import uuid
from typing import Any

from app.logging_config import logger

# Cache for API key SHA-256 hashes to avoid repeated computation
# Key: API key string, Value: SHA-256 hash (hex string)
_user_hash_cache: dict[str, str] = {}


def get_user_hash(api_key: str) -> str:
    """
    Get SHA-256 hash of API key with caching.
    
    This function caches the hash result to avoid repeated SHA-256 computation
    for the same API key, improving performance for high-frequency requests.
    
    Args:
        api_key: Provider API key to hash
    
    Returns:
        SHA-256 hash of the API key as hex string
        
    Examples:
        >>> key = "sk-test-key"
        >>> hash1 = get_user_hash(key)
        >>> hash2 = get_user_hash(key)
        >>> hash1 == hash2
        True
        >>> len(hash1)
        64
    """
    if api_key not in _user_hash_cache:
        # Compute and cache the hash
        _user_hash_cache[api_key] = hashlib.sha256(api_key.encode()).hexdigest()
        logger.debug(
            "claude_cli: computed and cached API key hash cache_size=%d",
            len(_user_hash_cache),
        )
    else:
        logger.debug(
            "claude_cli: using cached API key hash cache_size=%d",
            len(_user_hash_cache),
        )

    return _user_hash_cache[api_key]


def generate_claude_cli_user_id(api_key: str, session_id: str | None = None) -> str:
    """
    Generate Claude Code CLI format user_id.
    
    Format: user_{sha256(api_key)}_account__session_{uuid}
    
    Args:
        api_key: Provider API key
        session_id: Optional session UUID, generates new if not provided
    
    Returns:
        Formatted user_id string
        
    Examples:
        >>> api_key = "sk-test-key"
        >>> user_id = generate_claude_cli_user_id(api_key, "test-session-id")
        >>> user_id.startswith("user_")
        True
        >>> user_id.endswith("_account__session_test-session-id")
        True
    """
    # Get SHA-256 hash of API key (with caching)
    user_hash = get_user_hash(api_key)

    # Generate or use provided session ID
    generated_session = False
    if session_id is None:
        session_id = str(uuid.uuid4())
        generated_session = True

    # Return formatted user_id
    user_id = f"user_{user_hash}_account__session_{session_id}"

    # Log user_id generation (redacted for security)
    logger.debug(
        "claude_cli: generated user_id prefix=%s session_id=%s generated_session=%s",
        user_id[:20] + "...",  # Only show first 20 chars
        session_id,
        generated_session,
    )

    return user_id


def build_claude_cli_headers(api_key: str) -> dict[str, str]:
    """
    Build complete Claude Code CLI request headers.
    
    Args:
        api_key: Provider API key
    
    Returns:
        Dictionary of HTTP headers matching Claude CLI client
        
    Examples:
        >>> headers = build_claude_cli_headers("sk-test")
        >>> headers["User-Agent"]
        'claude-cli/2.0.62 (external, claude-vscode, agent-sdk/0.1.62)'
        >>> headers["X-Api-Key"]
        'sk-test'
    """
    return {
        "Accept": "application/json",
        "Anthropic-Beta": "interleaved-thinking-2025-05-14,tool-examples-2025-10-29",
        "Anthropic-Dangerous-Direct-Browser-Access": "true",
        "Anthropic-Version": "2023-06-01",
        "Content-Type": "application/json",
        "User-Agent": "claude-cli/2.0.62 (external, claude-vscode, agent-sdk/0.1.62)",
        "X-Api-Key": api_key,
        "X-App": "cli",
        "X-Stainless-Arch": "x64",
        "X-Stainless-Lang": "js",
        "X-Stainless-Os": "Linux",
        "X-Stainless-Package-Version": "0.70.0",
        "X-Stainless-Retry-Count": "0",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "v24.3.0",
        "X-Stainless-Timeout": "600",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive"
    }


def transform_to_claude_cli_format(
    payload: dict[str, Any],
    api_key: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Transform OpenAI-style payload to Claude CLI format.
    
    Args:
        payload: Original request payload (OpenAI format)
        api_key: Provider API key for user_id generation
        session_id: Optional session ID for user_id
    
    Returns:
        Transformed payload in Claude CLI format
        
    Examples:
        >>> payload = {
        ...     "model": "claude-3-5-sonnet-20241022",
        ...     "messages": [{"role": "user", "content": "Hello"}]
        ... }
        >>> result = transform_to_claude_cli_format(payload, "sk-test")
        >>> result["messages"][0]["content"][0]["type"]
        'text'
        >>> "metadata" in result
        True
        >>> "user_id" in result["metadata"]
        True
    """
    logger.info(
        "claude_cli: transforming request to Claude CLI format model=%s stream=%s message_count=%d",
        payload.get("model"),
        payload.get("stream", False),
        len(payload.get("messages", [])),
    )

    # Create a copy to avoid modifying the original
    transformed = dict(payload)

    # Track transformations for logging
    messages_transformed = 0
    system_transformed = False

    # Ensure messages content is in array format
    if "messages" in transformed:
        for msg in transformed["messages"]:
            if isinstance(msg.get("content"), str):
                # Convert string content to Claude array format
                msg["content"] = [
                    {
                        "type": "text",
                        "text": msg["content"]
                    }
                ]
                messages_transformed += 1

    # Ensure system is in array format
    if "system" in transformed and isinstance(transformed["system"], str):
        transformed["system"] = [
            {
                "type": "text",
                "text": transformed["system"]
            }
        ]
        system_transformed = True

    # Add empty tools array if not present
    if "tools" not in transformed:
        transformed["tools"] = []

    # Add temperature if not present (Claude CLI default)
    if "temperature" not in transformed:
        transformed["temperature"] = 1
        logger.debug("claude_cli: added default temperature=1")

    # Generate and add user_id in metadata
    user_id = generate_claude_cli_user_id(api_key, session_id)

    if "metadata" not in transformed:
        transformed["metadata"] = {}

    transformed["metadata"]["user_id"] = user_id

    logger.debug(
        "claude_cli: transformation complete messages_transformed=%d system_transformed=%s "
        "tools_added=%s temperature=%s user_id_prefix=%s",
        messages_transformed,
        system_transformed,
        "tools" not in payload,
        transformed.get("temperature"),
        user_id[:20] + "...",
    )

    return transformed


def transform_claude_response_to_openai(
    claude_response: dict[str, Any],
    original_model: str,
) -> dict[str, Any]:
    """
    Transform Claude API response to OpenAI format.
    
    Args:
        claude_response: Response from Claude API
        original_model: Original model name from request
    
    Returns:
        OpenAI-formatted response
        
    Examples:
        >>> claude_resp = {
        ...     "id": "msg_123",
        ...     "content": [{"type": "text", "text": "Hello!"}],
        ...     "stop_reason": "end_turn",
        ...     "usage": {"input_tokens": 10, "output_tokens": 5}
        ... }
        >>> result = transform_claude_response_to_openai(claude_resp, "claude-3-5-sonnet")
        >>> result["object"]
        'chat.completion'
        >>> result["choices"][0]["message"]["content"]
        'Hello!'
        >>> result["usage"]["total_tokens"]
        15
    """
    # If already in OpenAI format, return as-is
    if "choices" in claude_response:
        logger.debug(
            "claude_cli: response already in OpenAI format, skipping transformation"
        )
        return claude_response

    logger.info(
        "claude_cli: transforming Claude response to OpenAI format response_id=%s "
        "stop_reason=%s has_usage=%s",
        claude_response.get("id", "unknown"),
        claude_response.get("stop_reason", "unknown"),
        "usage" in claude_response,
    )

    # Transform Claude format to OpenAI format
    openai_response = {
        "id": claude_response.get("id", ""),
        "object": "chat.completion",
        "created": int(claude_response.get("created_at", 0)),
        "model": original_model,
        "choices": [],
        "usage": {}
    }

    # Transform content
    content_blocks_count = 0
    text_blocks_count = 0
    if "content" in claude_response:
        content_blocks = claude_response["content"]
        content_blocks_count = len(content_blocks)
        text_parts = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
                text_blocks_count += 1

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

    # Transform usage
    if "usage" in claude_response:
        usage = claude_response["usage"]
        openai_response["usage"] = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        }

    logger.debug(
        "claude_cli: response transformation complete content_blocks=%d text_blocks=%d "
        "prompt_tokens=%d completion_tokens=%d",
        content_blocks_count,
        text_blocks_count,
        openai_response["usage"].get("prompt_tokens", 0),
        openai_response["usage"].get("completion_tokens", 0),
    )

    return openai_response
