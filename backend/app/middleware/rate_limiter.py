"""
Rate limiting middleware to prevent brute force and DDoS attacks.
"""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = object  # type: ignore[misc,assignment]


class InMemoryRateLimiter:
    """
    内存版限流器（适用于单实例或开发环境）。
    
    使用滑动窗口算法，记录每个 IP 在时间窗口内的请求次数。
    """

    def __init__(self):
        # {ip: [(timestamp, count), ...]}
        self._requests: dict[str, list[tuple[float, int]]] = defaultdict(list)

    async def is_rate_limited(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        检查是否超过限流阈值。
        
        Args:
            key: 限流键（通常是 IP 地址）
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
        
        Returns:
            (is_limited, remaining, reset_time)
        """
        now = time.time()
        cutoff = now - window_seconds

        # 清理过期记录
        self._requests[key] = [
            (ts, count) for ts, count in self._requests[key] if ts > cutoff
        ]

        # 计算当前窗口内的请求数
        current_count = sum(count for _, count in self._requests[key])

        if current_count >= max_requests:
            # 计算重置时间（最早请求的过期时间）
            if self._requests[key]:
                oldest_ts = min(ts for ts, _ in self._requests[key])
                reset_time = int(oldest_ts + window_seconds)
            else:
                reset_time = int(now + window_seconds)
            return True, 0, reset_time

        # 记录本次请求
        self._requests[key].append((now, 1))
        remaining = max_requests - current_count - 1
        reset_time = int(now + window_seconds)

        return False, remaining, reset_time

    async def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """定期清理过期数据（可选的后台任务）"""
        now = time.time()
        cutoff = now - max_age_seconds
        keys_to_delete = []

        for key, requests in self._requests.items():
            self._requests[key] = [(ts, count) for ts, count in requests if ts > cutoff]
            if not self._requests[key]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._requests[key]


class RedisRateLimiter:
    """
    Redis 版限流器（适用于分布式部署）。
    
    使用 Redis 的原子操作实现分布式限流。
    """

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def is_rate_limited(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        检查是否超过限流阈值（Redis 版本）。
        """
        now = time.time()
        redis_key = f"ratelimit:{key}"

        # 使用 Redis 的 ZSET 实现滑动窗口
        pipe = self.redis.pipeline()

        # 移除过期的请求记录
        cutoff = now - window_seconds
        pipe.zremrangebyscore(redis_key, 0, cutoff)

        # 获取当前窗口内的请求数
        pipe.zcard(redis_key)

        # 添加当前请求
        pipe.zadd(redis_key, {str(now): now})

        # 设置过期时间
        pipe.expire(redis_key, window_seconds + 10)

        results = await pipe.execute()
        current_count = results[1]  # ZCARD 的结果

        if current_count >= max_requests:
            # 获取最早的请求时间
            oldest = await self.redis.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                oldest_ts = oldest[0][1]
                reset_time = int(oldest_ts + window_seconds)
            else:
                reset_time = int(now + window_seconds)
            return True, 0, reset_time

        remaining = max_requests - current_count - 1
        reset_time = int(now + window_seconds)
        return False, remaining, reset_time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    限流中间件，防止暴力破解和 DDoS 攻击。
    
    支持：
    - 基于 IP 的全局限流
    - 基于路径的特定限流（如登录接口）
    - 内存或 Redis 存储
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Redis | None = None,
        default_max_requests: int | None = None,
        default_window_seconds: int = 60,
        path_limits: dict[str, tuple[int, int]] | None = None,
        get_client_ip: Callable[[Request], str] | None = None,
    ):
        """
        Args:
            app: ASGI 应用
            redis_client: Redis 客户端（可选，不提供则使用内存存储）
            default_max_requests: 默认时间窗口内最大请求数
            default_window_seconds: 默认时间窗口（秒）
            path_limits: 特定路径的限流配置 {path: (max_requests, window_seconds)}
            get_client_ip: 自定义获取客户端 IP 的函数
        """
        super().__init__(app)

        if redis_client:
            self.limiter = RedisRateLimiter(redis_client)
        else:
            self.limiter = InMemoryRateLimiter()

        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        self.path_limits = path_limits or {}
        self.get_client_ip = get_client_ip or self._default_get_client_ip

    def _default_get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实 IP。
        
        优先级：
        1. X-Forwarded-For（代理/负载均衡器）
        2. X-Real-IP（Nginx）
        3. request.client.host（直连）
        """
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For 可能包含多个 IP，取第一个
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # 直连 IP
        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查和静态资源
        if request.url.path in ["/health", "/metrics", "/favicon.ico"]:
            return await call_next(request)

        # 获取客户端 IP
        client_ip = self.get_client_ip(request)

        # 确定限流参数
        path = request.url.path
        # 默认限流阈值：显式传入的 default_max_requests 优先，
        # 未提供时才回退到 settings.gateway_max_concurrent_requests。
        max_requests = self.default_max_requests
        if max_requests is None:
            max_requests = getattr(settings, "gateway_max_concurrent_requests", None)
        if max_requests is None:
            max_requests = 1000
        window_seconds = self.default_window_seconds

        # 检查是否有特定路径的限流配置
        for path_pattern, (max_req, window) in self.path_limits.items():
            if path.startswith(path_pattern):
                max_requests = max_req
                window_seconds = window
                break

        # 执行限流检查
        rate_limit_key = f"{client_ip}:{path}"
        is_limited, remaining, reset_time = await self.limiter.is_rate_limited(
            rate_limit_key, max_requests, window_seconds
        )

        # 添加限流响应头
        headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        if is_limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": reset_time - int(time.time()),
                },
                headers={
                    **headers,
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )

        # 继续处理请求
        response: Response = await call_next(request)

        # 添加限流信息到响应头
        for key, value in headers.items():
            response.headers[key] = value

        return response
