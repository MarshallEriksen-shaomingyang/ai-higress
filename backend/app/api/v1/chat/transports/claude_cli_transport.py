"""
Claude CLI 传输层实现：使用 Claude CLI 格式调用
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import status
from sqlalchemy.orm import Session as DbSession

from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.models import ProviderKey
from app.provider.config import ProviderConfig
from app.services.claude_cli_transformer import (
    build_claude_cli_headers,
    transform_claude_response_to_openai,
    transform_to_claude_cli_format,
)
from app.services.metrics_service import (
    call_upstream_http_with_metrics,
    stream_upstream_with_metrics,
)

from .base import Transport, TransportResult


class ClaudeCliTransport(Transport):
    """Claude CLI 传输层实现"""

    def __init__(
        self,
        *,
        api_key: AuthenticatedAPIKey,
        client: httpx.AsyncClient,
        db: DbSession,
        session_id: str | None = None,
        logical_model: str | None = None,
    ):
        super().__init__(
            api_key=api_key,
            session_id=session_id,
            logical_model=logical_model,
        )
        self.client = client
        self.db = db

    def supports_provider(self, provider_id: str) -> bool:
        """Claude CLI 传输支持所有 Claude Provider"""
        return "claude" in provider_id.lower()

    async def send_request(
        self,
        *,
        provider_id: str,
        provider_key: ProviderKey,
        provider_model_id: str,
        payload: dict[str, Any],
        is_stream: bool,
        provider_config: ProviderConfig,
        **kwargs: Any,
    ) -> TransportResult:
        """
        使用 Claude CLI 格式发送请求
        
        Args:
            provider_id: Provider ID
            provider_key: Provider Key 对象
            provider_model_id: Provider 的模型 ID
            payload: 请求 payload
            is_stream: 是否为流式请求
            provider_config: Provider 配置
            **kwargs: 其他参数
        
        Returns:
            TransportResult: 传输结果
        """
        # 构建 Claude CLI 请求
        try:
            claude_cli_headers = build_claude_cli_headers(provider_key.key)
            claude_payload = transform_to_claude_cli_format(
                payload,
                api_key=provider_key.key,
                session_id=self.session_id,
            )
        except Exception as exc:
            logger.error(
                "claude_cli_transport: failed to build request provider=%s model=%s error=%s",
                provider_id,
                provider_model_id,
                exc,
                exc_info=True,
            )
            return TransportResult(
                error=f"Failed to build Claude CLI request: {exc}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 构建 URL
        base_url = str(provider_config.base_url).rstrip("/")
        claude_url = f"{base_url}/v1/messages?beta=true"

        logger.info(
            "claude_cli_transport: sending %s request provider=%s model=%s url=%s",
            "streaming" if is_stream else "non-streaming",
            provider_id,
            provider_model_id,
            claude_url,
        )

        if is_stream:
            return await self._send_streaming_request(
                provider_id=provider_id,
                provider_model_id=provider_model_id,
                url=claude_url,
                headers=claude_cli_headers,
                payload=claude_payload,
                original_model=payload.get("model", provider_model_id),
            )
        else:
            return await self._send_non_streaming_request(
                provider_id=provider_id,
                provider_model_id=provider_model_id,
                url=claude_url,
                headers=claude_cli_headers,
                payload=claude_payload,
                original_model=payload.get("model", provider_model_id),
            )

    async def _send_non_streaming_request(
        self,
        *,
        provider_id: str,
        provider_model_id: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        original_model: str,
    ) -> TransportResult:
        """发送非流式 Claude CLI 请求"""
        try:
            r = await call_upstream_http_with_metrics(
                client=self.client,
                url=url,
                headers=headers,
                json_body=payload,
                db=self.db,
                provider_id=provider_id,
                logical_model=self.logical_model or "",
                user_id=self.api_key.user_id,
                api_key_id=self.api_key.id,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "claude_cli_transport: request error provider=%s model=%s error=%s",
                provider_id,
                provider_model_id,
                exc,
            )
            return TransportResult(
                error=str(exc),
                status_code=500,
            )

        status_code = r.status_code
        text = r.text

        logger.info(
            "claude_cli_transport: response status=%s provider=%s model=%s body_length=%d",
            status_code,
            provider_id,
            provider_model_id,
            len(text or ""),
        )

        # 解析响应
        try:
            claude_response = r.json()
        except ValueError:
            claude_response = {"raw": text}

        # 转换为 OpenAI 格式
        if isinstance(claude_response, dict) and "content" in claude_response:
            openai_response = transform_claude_response_to_openai(
                claude_response,
                original_model,
            )
        else:
            openai_response = claude_response

        return TransportResult(
            response=openai_response,
            status_code=status_code,
            provider_model_id=provider_model_id,
        )

    async def _send_streaming_request(
        self,
        *,
        provider_id: str,
        provider_model_id: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        original_model: str,
    ) -> TransportResult:
        """发送流式 Claude CLI 请求"""

        async def stream_wrapper() -> AsyncIterator[bytes]:
            try:
                async for chunk in stream_upstream_with_metrics(
                    client=self.client,
                    url=url,
                    headers=headers,
                    json_body=payload,
                    db=self.db,
                    provider_id=provider_id,
                    logical_model=self.logical_model or "",
                    user_id=self.api_key.user_id,
                    api_key_id=self.api_key.id,
                ):
                    # Claude CLI 流式响应可能需要转换
                    # 这里简化处理，直接转发
                    yield chunk
            except Exception as exc:
                logger.exception(
                    "claude_cli_transport: streaming error provider=%s model=%s",
                    provider_id,
                    provider_model_id,
                )
                error_payload = {
                    "error": {
                        "code": "CLAUDE_CLI_ERROR",
                        "message": str(exc),
                    }
                }
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode()

        return TransportResult(
            stream=stream_wrapper(),
            is_stream=True,
            status_code=200,
            provider_model_id=provider_model_id,
        )
