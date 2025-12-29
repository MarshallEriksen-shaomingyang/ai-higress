"""
聊天路由模块化拆分

将原 chat_routes.py 中的复杂逻辑按职责拆分到不同模块：
- middleware: 请求预处理、内容审核
- billing: 计费逻辑
- transports: 不同传输方式的实现（HTTP/SDK/Claude CLI）
- candidate_retry: 候选 Provider 重试逻辑
- utils: 工具函数（payload 标准化、响应转换）
- provider_selector: Provider 选择器（Phase 3）
- request_handler: 请求处理协调器（Phase 3）
"""

from .billing import record_completion_usage, record_stream_usage
from .middleware import (
    apply_response_moderation,
    enforce_request_moderation,
    wrap_stream_with_moderation,
)
from .provider_selector import ProviderSelector
from .request_handler import RequestHandler
from .transports import (
    ClaudeCliTransport,
    HttpTransport,
    SdkTransport,
    Transport,
    TransportResult,
)
from .utils import (
    convert_claude_response,
    convert_gemini_response,
    detect_api_style,
    normalize_payload,
)

__all__ = [
    # Middleware
    "enforce_request_moderation",
    "apply_response_moderation",
    "wrap_stream_with_moderation",
    # Billing
    "record_completion_usage",
    "record_stream_usage",
    # Transports
    "Transport",
    "TransportResult",
    "HttpTransport",
    "SdkTransport",
    "ClaudeCliTransport",
    # Utils
    "normalize_payload",
    "detect_api_style",
    "convert_gemini_response",
    "convert_claude_response",
    # Phase 3: Business Logic Layer
    "ProviderSelector",
    "RequestHandler",
]
