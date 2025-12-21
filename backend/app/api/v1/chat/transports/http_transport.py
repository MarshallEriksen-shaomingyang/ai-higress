"""
HTTP 传输层实现：标准 HTTP 请求处理

⚠️ 注意：这是一个基础实现，缺少以下高级功能：
1. Claude fallback 机制（需要在上层 request_handler 中实现）
2. Provider Key 管理（需要在上层实现）
3. Session 绑定（需要在上层实现）
4. Context 保存（需要在上层实现）
5. 可重试状态码判断（需要在上层实现）

这些功能应该由 request_handler.py 协调实现，而不是在传输层实现。
传输层只负责：发送请求、接收响应、基本的格式转换。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from sqlalchemy.orm import Session as DbSession

from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.services.metrics_service import (
    call_upstream_http_with_metrics,
    stream_upstream_with_metrics,
)
from app.upstream import UpstreamStreamError

from ..utils import convert_gemini_response, normalize_payload
from .base import Transport, TransportResult


class HttpTransport(Transport):
    """
    HTTP 传输层实现
    
    职责：
    - 发送 HTTP 请求到上游
    - 接收响应并返回
    - 基本的响应格式转换（Gemini -> OpenAI）
    - 错误处理和日志记录
    
    不负责：
    - Provider Key 管理（由上层处理）
    - Session 绑定（由上层处理）
    - Claude fallback（由上层处理）
    - 重试逻辑（由上层处理）
    """

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
        """HTTP 传输支持所有 Provider"""
        return True

    async def send_request(
        self,
        *,
        provider_id: str,
        provider_key: str,  # 直接传入 key 字符串，而不是 ProviderKey 对象
        provider_model_id: str,
        payload: dict[str, Any],
        is_stream: bool,
        endpoint: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> TransportResult:
        """
        发送 HTTP 请求到上游 Provider
        
        Args:
            provider_id: Provider ID
            provider_key: Provider API Key（字符串）
            provider_model_id: Provider 的模型 ID
            payload: 请求 payload
            is_stream: 是否为流式请求
            endpoint: 上游端点 URL
            headers: 请求头
            **kwargs: 其他参数（如 api_style, fallback_url 等）
        
        Returns:
            TransportResult: 传输结果
        """
        # 标准化 payload（替换模型名称）
        upstream_payload = normalize_payload(
            payload,
            provider_model_id=provider_model_id,
        )

        # 准备请求头
        request_headers = headers or {}

        logger.info(
            "http_transport: sending %s request to provider=%s model=%s url=%s",
            "streaming" if is_stream else "non-streaming",
            provider_id,
            provider_model_id,
            endpoint,
        )

        if is_stream:
            return await self._send_streaming_request(
                provider_id=provider_id,
                provider_model_id=provider_model_id,
                endpoint=endpoint,
                headers=request_headers,
                payload=upstream_payload,
            )
        else:
            return await self._send_non_streaming_request(
                provider_id=provider_id,
                provider_model_id=provider_model_id,
                endpoint=endpoint,
                headers=request_headers,
                payload=upstream_payload,
                original_payload=payload,
            )

    async def _send_non_streaming_request(
        self,
        *,
        provider_id: str,
        provider_model_id: str,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        original_payload: dict[str, Any],
    ) -> TransportResult:
        """
        发送非流式请求
        
        Returns:
            TransportResult: 包含响应数据或错误信息
            - 成功：response 字段包含响应数据，status_code 为实际状态码
            - 失败：error 字段包含错误信息，status_code 为错误状态码
        """
        try:
            r = await call_upstream_http_with_metrics(
                client=self.client,
                url=endpoint,
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
                "http_transport: upstream request error for %s (provider=%s, model=%s): %s",
                endpoint,
                provider_id,
                provider_model_id,
                exc,
            )
            # 网络错误：返回错误结果，由上层决定是否重试
            return TransportResult(
                error=str(exc),
                status_code=None,  # 网络错误没有 HTTP 状态码
                provider_model_id=provider_model_id,
            )

        status_code = r.status_code
        text = r.text

        logger.info(
            "http_transport: upstream response status=%s provider=%s model=%s body_length=%d",
            status_code,
            provider_id,
            provider_model_id,
            len(text or ""),
        )

        # 解析响应
        try:
            response_data = r.json()
        except ValueError:
            # JSON 解析失败，返回原始文本
            response_data = {"raw": text}

        # Gemini 响应转换
        if isinstance(response_data, dict) and response_data.get("candidates") is not None:
            # 检测是否为 Gemini 响应格式
            if "gemini" in provider_model_id.lower():
                original_model = original_payload.get("model") or provider_model_id
                response_data = convert_gemini_response(response_data, original_model)

        # 返回结果（包括错误状态码）
        # 上层会根据 status_code 判断是否需要重试或 fallback
        return TransportResult(
            response=response_data,
            status_code=status_code,
            provider_model_id=provider_model_id,
            error=text if status_code >= 400 else None,
        )

    async def _send_streaming_request(
        self,
        *,
        provider_id: str,
        provider_model_id: str,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> TransportResult:
        """
        发送流式请求
        
        Returns:
            TransportResult: 包含流式响应迭代器
            - stream 字段包含 AsyncIterator[bytes]
            - 流式错误会在迭代器中以 SSE 错误帧形式返回
        """

        async def stream_wrapper() -> AsyncIterator[bytes]:
            try:
                async for chunk in stream_upstream_with_metrics(
                    client=self.client,
                    url=endpoint,
                    headers=headers,
                    json_body=payload,
                    db=self.db,
                    provider_id=provider_id,
                    logical_model=self.logical_model or "",
                    user_id=self.api_key.user_id,
                    api_key_id=self.api_key.id,
                ):
                    yield chunk
            except UpstreamStreamError as exc:
                logger.warning(
                    "http_transport: upstream streaming error for %s (provider=%s, model=%s): %s",
                    endpoint,
                    provider_id,
                    provider_model_id,
                    exc,
                )
                # 流式错误：返回错误帧
                # 注意：这个错误发生在流开始之前，上层可以捕获并重试
                error_payload = {
                    "error": {
                        "code": "UPSTREAM_ERROR",
                        "message": str(exc),
                        "status_code": exc.status_code,
                    }
                }
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode()
            except Exception as exc:
                logger.exception(
                    "http_transport: unexpected streaming error for %s (provider=%s, model=%s)",
                    endpoint,
                    provider_id,
                    provider_model_id,
                )
                error_payload = {
                    "error": {
                        "code": "INTERNAL_ERROR",
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
