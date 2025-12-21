"""
Security headers middleware to protect against common web vulnerabilities.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    添加安全响应头，防护常见 Web 攻击。
    
    包含的安全头：
    - X-Content-Type-Options: 防止 MIME 类型嗅探
    - X-Frame-Options: 防止点击劫持
    - X-XSS-Protection: 启用 XSS 过滤
    - Strict-Transport-Security: 强制 HTTPS（生产环境）
    - Content-Security-Policy: 内容安全策略
    - Referrer-Policy: 控制 Referer 信息泄露
    - Permissions-Policy: 限制浏览器功能
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = False,
        hsts_max_age: int = 31536000,
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 防止 MIME 类型嗅探攻击
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 防止点击劫持攻击
        response.headers["X-Frame-Options"] = "DENY"

        # XSS 保护（虽然现代浏览器已弃用，但保留兼容性）
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 内容安全策略（根据实际需求调整）
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Referrer 策略
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 权限策略（禁用不必要的浏览器功能）
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        # HSTS（仅在 HTTPS 环境启用）
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # 隐藏服务器信息
        if "Server" in response.headers:
            del response.headers["Server"]

        return response
