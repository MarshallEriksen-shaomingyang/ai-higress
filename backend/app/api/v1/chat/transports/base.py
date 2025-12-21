"""
传输层基类和接口定义
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.auth import AuthenticatedAPIKey
from app.models import ProviderKey


@dataclass
class TransportResult:
    """传输层返回结果"""

    # 响应数据
    response: dict[str, Any] | None = None

    # 流式响应迭代器
    stream: AsyncIterator[bytes] | None = None

    # 是否为流式响应
    is_stream: bool = False

    # HTTP 状态码
    status_code: int = 200

    # 实际使用的 Provider Key
    provider_key: ProviderKey | None = None

    # 实际使用的模型 ID
    provider_model_id: str | None = None

    # 错误信息（如果有）
    error: str | None = None


class Transport(ABC):
    """传输层基类"""

    def __init__(
        self,
        *,
        api_key: AuthenticatedAPIKey,
        session_id: str | None = None,
        logical_model: str | None = None,
    ):
        self.api_key = api_key
        self.session_id = session_id
        self.logical_model = logical_model

    @abstractmethod
    async def send_request(
        self,
        *,
        provider_id: str,
        provider_key: ProviderKey,
        provider_model_id: str,
        payload: dict[str, Any],
        is_stream: bool,
        **kwargs: Any,
    ) -> TransportResult:
        """
        发送请求到上游 Provider
        
        Args:
            provider_id: Provider ID
            provider_key: Provider Key 对象
            provider_model_id: Provider 的模型 ID
            payload: 请求 payload
            is_stream: 是否为流式请求
            **kwargs: 其他传输层特定参数
        
        Returns:
            TransportResult: 传输结果
        """
        pass

    @abstractmethod
    def supports_provider(self, provider_id: str) -> bool:
        """
        检查是否支持指定的 Provider
        
        Args:
            provider_id: Provider ID
        
        Returns:
            bool: 是否支持
        """
        pass
