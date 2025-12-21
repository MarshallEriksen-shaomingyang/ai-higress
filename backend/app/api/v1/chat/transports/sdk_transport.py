"""
SDK 传输层实现：使用 SDK 驱动调用上游
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session as DbSession

from app.auth import AuthenticatedAPIKey
from app.logging_config import logger
from app.models import ProviderKey
from app.provider.config import ProviderConfig
from app.provider.sdk_selector import get_sdk_driver, normalize_base_url
from app.services.metrics_service import (
    call_sdk_generate_with_metrics,
    stream_sdk_with_metrics,
)

from .base import Transport, TransportResult


class SdkTransport(Transport):
    """SDK 传输层实现"""

    def __init__(
        self,
        *,
        api_key: AuthenticatedAPIKey,
        db: DbSession,
        session_id: str | None = None,
        logical_model: str | None = None,
    ):
        super().__init__(
            api_key=api_key,
            session_id=session_id,
            logical_model=logical_model,
        )
        self.db = db

    def supports_provider(self, provider_id: str) -> bool:
        """检查 Provider 是否支持 SDK 传输"""
        from app.provider.config import get_provider_config

        provider_cfg = get_provider_config(provider_id)
        if provider_cfg is None:
            return False

        return getattr(provider_cfg, "transport", "http") == "sdk"

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
        使用 SDK 发送请求到上游 Provider
        
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
        # 获取 SDK 驱动
        driver = get_sdk_driver(provider_config)
        if driver is None:
            logger.error(
                "sdk_transport: provider=%s does not support SDK transport",
                provider_id,
            )
            return TransportResult(
                error=f"Provider '{provider_id}' 不支持 transport=sdk",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info(
            "sdk_transport: calling %s request provider=%s model=%s driver=%s",
            "streaming" if is_stream else "non-streaming",
            provider_id,
            provider_model_id,
            driver.name,
        )

        if is_stream:
            return await self._send_streaming_request(
                driver=driver,
                provider_id=provider_id,
                provider_key=provider_key,
                provider_model_id=provider_model_id,
                payload=payload,
                base_url=normalize_base_url(provider_config.base_url),
            )
        else:
            return await self._send_non_streaming_request(
                driver=driver,
                provider_id=provider_id,
                provider_key=provider_key,
                provider_model_id=provider_model_id,
                payload=payload,
                base_url=normalize_base_url(provider_config.base_url),
            )

    async def _send_non_streaming_request(
        self,
        *,
        driver: Any,
        provider_id: str,
        provider_key: ProviderKey,
        provider_model_id: str,
        payload: dict[str, Any],
        base_url: str | None,
    ) -> TransportResult:
        """发送非流式 SDK 请求"""
        try:
            sdk_payload = await call_sdk_generate_with_metrics(
                driver=driver,
                api_key=provider_key.key,
                model_id=provider_model_id,
                payload=payload,
                base_url=base_url,
                db=self.db,
                provider_id=provider_id,
                logical_model=self.logical_model or "",
                user_id=self.api_key.user_id,
                api_key_id=self.api_key.id,
            )
        except Exception as exc:
            logger.warning(
                "sdk_transport: error provider=%s model=%s error=%s",
                provider_id,
                provider_model_id,
                exc,
            )
            return TransportResult(
                error=str(exc),
                status_code=500,
            )

        logger.info(
            "sdk_transport: success provider=%s model=%s",
            provider_id,
            provider_model_id,
        )

        return TransportResult(
            response=sdk_payload,
            status_code=200,
            provider_model_id=provider_model_id,
        )

    async def _send_streaming_request(
        self,
        *,
        driver: Any,
        provider_id: str,
        provider_key: ProviderKey,
        provider_model_id: str,
        payload: dict[str, Any],
        base_url: str | None,
    ) -> TransportResult:
        """发送流式 SDK 请求"""

        async def stream_wrapper() -> AsyncIterator[bytes]:
            try:
                async for chunk_dict in stream_sdk_with_metrics(
                    driver=driver,
                    api_key=provider_key.key,
                    model_id=provider_model_id,
                    payload=payload,
                    base_url=base_url,
                    db=self.db,
                    provider_id=provider_id,
                    logical_model=self.logical_model or "",
                    user_id=self.api_key.user_id,
                    api_key_id=self.api_key.id,
                ):
                    # SDK 驱动返回的是字典，需要转换为 SSE 格式
                    chunk_json = json.dumps(chunk_dict, ensure_ascii=False)
                    yield f"data: {chunk_json}\n\n".encode()
            except Exception as exc:
                logger.exception(
                    "sdk_transport: streaming error provider=%s model=%s",
                    provider_id,
                    provider_model_id,
                )
                error_payload = {
                    "error": {
                        "code": "SDK_ERROR",
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
