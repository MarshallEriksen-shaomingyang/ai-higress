"""
HTTP 客户端抽象层，使用 curl-cffi 支持 TLS 指纹伪装。

本模块提供了一个与 httpx 兼容的 HTTP 客户端封装，用于替代原有的 httpx.AsyncClient。
主要用于 Claude CLI 传输模式，支持浏览器 TLS 指纹伪装。
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from curl_cffi.const import CurlECode, CurlHttpVersion
from curl_cffi.curl import CurlError
from curl_cffi.requests import AsyncSession, Response

logger = logging.getLogger(__name__)

_HTTP_VERSION_ALIASES: dict[str, CurlHttpVersion] = {
    "1": CurlHttpVersion.V1_0,
    "1.0": CurlHttpVersion.V1_0,
    "http/1": CurlHttpVersion.V1_0,
    "http/1.0": CurlHttpVersion.V1_0,
    "v1_0": CurlHttpVersion.V1_0,
    "v1.0": CurlHttpVersion.V1_0,
    "1.1": CurlHttpVersion.V1_1,
    "http/1.1": CurlHttpVersion.V1_1,
    "v1_1": CurlHttpVersion.V1_1,
    "v1.1": CurlHttpVersion.V1_1,
    "2": CurlHttpVersion.V2_0,
    "2.0": CurlHttpVersion.V2_0,
    "http/2": CurlHttpVersion.V2_0,
    "http/2.0": CurlHttpVersion.V2_0,
    "h2": CurlHttpVersion.V2_0,
    "v2_0": CurlHttpVersion.V2_0,
    "v2.0": CurlHttpVersion.V2_0,
    "2tls": CurlHttpVersion.V2TLS,
    "v2tls": CurlHttpVersion.V2TLS,
    "2_prior_knowledge": CurlHttpVersion.V2_PRIOR_KNOWLEDGE,
    "2-prior-knowledge": CurlHttpVersion.V2_PRIOR_KNOWLEDGE,
    "v2_prior_knowledge": CurlHttpVersion.V2_PRIOR_KNOWLEDGE,
    "3": CurlHttpVersion.V3,
    "3.0": CurlHttpVersion.V3,
    "http/3": CurlHttpVersion.V3,
    "http/3.0": CurlHttpVersion.V3,
    "h3": CurlHttpVersion.V3,
    "v3": CurlHttpVersion.V3,
    "3only": CurlHttpVersion.V3ONLY,
    "v3only": CurlHttpVersion.V3ONLY,
}


def _normalize_http_version(value: Any) -> Any:
    """
    curl-cffi 的 `http_version` 最终会传给 libcurl 的 `CURLOPT_HTTP_VERSION`，
    需要是 int（或可被当作 int 使用的 IntEnum），不能是字符串。
    """
    if value is None:
        return None
    if isinstance(value, CurlHttpVersion):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _HTTP_VERSION_ALIASES:
            return int(_HTTP_VERSION_ALIASES[key])
        raise TypeError(
            f"Unsupported http_version string: {value!r}. "
            "Use CurlHttpVersion (recommended) or an int value."
        )
    raise TypeError(
        f"Unsupported http_version type: {type(value)!r}. "
        "Use CurlHttpVersion (recommended) or an int value."
    )


def _normalize_http_version_in_kwargs(request_kwargs: dict[str, Any]) -> dict[str, Any]:
    if "http_version" not in request_kwargs:
        return request_kwargs
    if request_kwargs.get("http_version") is None:
        return request_kwargs
    normalized = dict(request_kwargs)
    normalized["http_version"] = _normalize_http_version(normalized["http_version"])
    return normalized


class StreamResponse:
    """
    流式响应包装器，提供 httpx 兼容的异步上下文管理器接口。
    
    这个类包装了 curl-cffi 的流式响应，使其可以像 httpx.Response 一样使用：
    
    async with client.stream(...) as resp:
        async for chunk in resp.aiter_bytes():
            ...
    """

    def __init__(self, response: Response):
        """
        初始化流式响应包装器。
        
        Args:
            response: curl-cffi 的 Response 对象
        """
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers

    async def __aenter__(self) -> "StreamResponse":
        """进入异步上下文管理器。"""
        return self

    async def __aexit__(self, *args) -> None:
        """退出异步上下文管理器，关闭响应。"""
        # curl-cffi 的 Response 会在 stream context 退出时自动关闭
        pass

    async def aiter_bytes(self, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """
        异步迭代响应数据块。
        
        Args:
            chunk_size: 每次读取的字节数（curl-cffi 可能忽略此参数）
        
        Yields:
            bytes: 响应数据块
        """
        async for chunk in self._response.aiter_content(chunk_size=chunk_size):
            yield chunk

    async def aread(self) -> bytes:
        """
        读取完整的响应体。
        
        Returns:
            bytes: 完整的响应数据
        """
        return await self._response.acontent()


class CurlCffiClient:
    """
    curl-cffi AsyncSession 的封装类，提供 httpx 兼容的 API。
    
    支持 TLS 指纹伪装（impersonate），用于模拟真实浏览器的 TLS 握手特征。
    
    Args:
        timeout: 请求超时时间（秒）
        impersonate: 浏览器指纹类型，如 "chrome120", "safari15_5" 等
        trust_env: 是否信任环境变量中的代理配置
    
    Example:
        async with CurlCffiClient(timeout=30.0, impersonate="chrome120") as client:
            response = await client.post(
                "https://api.example.com/chat",
                json={"message": "Hello"},
                headers={"Authorization": "Bearer token"}
            )
    """

    def __init__(
        self,
        timeout: float = 30.0,
        impersonate: str = "chrome120",
        trust_env: bool = True,
        proxies: dict[str, str] | str | None = None,
    ):
        """
        初始化 CurlCffiClient。
        
        Args:
            timeout: 请求超时时间（秒），默认 30 秒
            impersonate: 浏览器指纹类型，默认 "chrome120"
            trust_env: 是否信任环境变量（HTTP_PROXY, HTTPS_PROXY 等），默认 True
            proxies: 代理配置，可以是字符串（单个代理）或字典（按协议配置）
                    例如: "http://localhost:3128" 或 {"http": "...", "https": "..."}
        """
        self.timeout = timeout
        self.impersonate = impersonate
        self.trust_env = trust_env
        self.proxies = proxies
        self._session: AsyncSession | None = None

        logger.debug(
            "CurlCffiClient initialized: timeout=%s, impersonate=%s, trust_env=%s, proxies=%s",
            timeout,
            impersonate,
            trust_env,
            "***" if proxies else None,  # 不记录完整代理 URL（可能包含密码）
        )

    async def __aenter__(self) -> "CurlCffiClient":
        """
        进入 async context manager，创建 AsyncSession。
        
        Returns:
            self: 返回客户端实例
        """
        self._session = AsyncSession()
        logger.debug("CurlCffiClient session created")
        return self

    async def __aexit__(self, *args) -> None:
        """
        退出 async context manager，关闭 AsyncSession。
        
        Args:
            *args: 异常信息（如果有）
        """
        if self._session:
            await self._session.close()
            logger.debug("CurlCffiClient session closed")
            self._session = None

    def _ensure_session(self) -> AsyncSession:
        """
        确保 session 已创建，否则抛出异常。
        
        Returns:
            AsyncSession: curl-cffi 的 AsyncSession 实例
        
        Raises:
            RuntimeError: 如果 session 未创建（未使用 async with）
        """
        if self._session is None:
            raise RuntimeError(
                "CurlCffiClient must be used as async context manager. "
                "Use 'async with CurlCffiClient(...) as client:'"
            )
        return self._session

    def _apply_proxy_kwargs(self, request_kwargs: dict[str, Any]) -> None:
        """
        将初始化时的代理配置合并到请求参数中。

        curl-cffi 的接口同时支持：
        - proxy: 单个代理字符串（内部会映射为 all）
        - proxies: 按协议映射的字典，例如 {"http": "...", "https": "...", "all": "..."}
        """
        if not self.proxies:
            return
        if isinstance(self.proxies, str):
            request_kwargs["proxy"] = self.proxies
        else:
            request_kwargs["proxies"] = self.proxies

    async def _request_with_optional_http2_downgrade(
        self,
        method: str,
        url: str,
        request_kwargs: dict[str, Any],
    ) -> Response:
        session = self._ensure_session()
        try:
            requester = getattr(session, method.lower())
            normalized_kwargs = _normalize_http_version_in_kwargs(request_kwargs)
            return await requester(url, **normalized_kwargs)
        except CurlError as exc:
            code = getattr(exc, "code", None)
            if (
                code == CurlECode.HTTP2_STREAM
                and "http_version" not in request_kwargs
                and request_kwargs.get("stream") is not True
            ):
                logger.warning(
                    "curl-cffi HTTP/2 stream protocol error, retry with HTTP/1.1: url=%s",
                    url,
                )
                retry_kwargs = dict(request_kwargs)
                retry_kwargs["http_version"] = "1.1"
                try:
                    requester = getattr(session, method.lower())
                    normalized_retry_kwargs = _normalize_http_version_in_kwargs(retry_kwargs)
                    return await requester(url, **normalized_retry_kwargs)
                except CurlError as retry_exc:
                    raise httpx.HTTPError(str(retry_exc)) from retry_exc
            raise httpx.HTTPError(str(exc)) from exc

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        **kwargs
    ) -> Response:
        """
        发送 POST 请求。
        
        Args:
            url: 请求 URL
            json: JSON 请求体（会自动序列化并设置 Content-Type）
            data: 原始请求体数据
            headers: 请求头字典
            timeout: 请求超时时间（秒），如果不指定则使用初始化时的 timeout
            **kwargs: 其他传递给 curl-cffi 的参数
        
        Returns:
            Response: curl-cffi 的 Response 对象
        
        Raises:
            RuntimeError: 如果 session 未创建
        """
        effective_timeout = timeout if timeout is not None else self.timeout

        logger.debug(
            "POST request: url=%s, timeout=%s, impersonate=%s, proxy=%s",
            url,
            effective_timeout,
            self.impersonate,
            "configured" if self.proxies else "none",
        )

        # 合并 proxies 参数
        request_kwargs = {
            "json": json,
            "data": data,
            "headers": headers,
            "timeout": effective_timeout,
            "impersonate": self.impersonate,
            **kwargs
        }
        self._apply_proxy_kwargs(request_kwargs)

        return await self._request_with_optional_http2_downgrade(
            "POST", url, request_kwargs
        )

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        **kwargs
    ) -> Response:
        """
        发送 GET 请求。
        
        Args:
            url: 请求 URL
            headers: 请求头字典
            params: URL 查询参数
            timeout: 请求超时时间（秒），如果不指定则使用初始化时的 timeout
            **kwargs: 其他传递给 curl-cffi 的参数
        
        Returns:
            Response: curl-cffi 的 Response 对象
        
        Raises:
            RuntimeError: 如果 session 未创建
        """
        effective_timeout = timeout if timeout is not None else self.timeout

        logger.debug(
            "GET request: url=%s, timeout=%s, impersonate=%s, proxy=%s",
            url,
            effective_timeout,
            self.impersonate,
            "configured" if self.proxies else "none",
        )

        # 合并 proxies 参数
        request_kwargs = {
            "headers": headers,
            "params": params,
            "timeout": effective_timeout,
            "impersonate": self.impersonate,
            **kwargs
        }
        self._apply_proxy_kwargs(request_kwargs)

        return await self._request_with_optional_http2_downgrade(
            "GET", url, request_kwargs
        )

    def stream(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        **kwargs
    ) -> "StreamContextManager":
        """
        发送流式请求，返回支持异步上下文管理器的响应对象。
        
        用法:
            async with client.stream("POST", url, json=data) as resp:
                async for chunk in resp.aiter_bytes():
                    ...
        
        Args:
            method: HTTP 方法（GET, POST 等）
            url: 请求 URL
            json: JSON 请求体（会自动序列化并设置 Content-Type）
            data: 原始请求体数据
            headers: 请求头字典
            timeout: 请求超时时间（秒），如果不指定则使用初始化时的 timeout
            **kwargs: 其他传递给 curl-cffi 的参数
        
        Returns:
            StreamContextManager: 支持异步上下文管理器的流式响应对象
        
        Raises:
            RuntimeError: 如果 session 未创建
        """
        session = self._ensure_session()

        effective_timeout = timeout if timeout is not None else self.timeout

        logger.debug(
            "STREAM request: method=%s, url=%s, timeout=%s, impersonate=%s, proxy=%s",
            method,
            url,
            effective_timeout,
            self.impersonate,
            "configured" if self.proxies else "none",
        )

        # 合并 proxies 参数
        request_kwargs = {
            "json": json,
            "data": data,
            "headers": headers,
            "timeout": effective_timeout,
            "impersonate": self.impersonate,
            **kwargs
        }
        self._apply_proxy_kwargs(request_kwargs)

        return StreamContextManager(session, method, url, request_kwargs)


class StreamContextManager:
    """
    流式请求的异步上下文管理器。
    
    这个类封装了 curl-cffi 的 stream 调用，使其可以像 httpx 一样使用：
    
    async with client.stream(...) as resp:
        if resp.status_code >= 400:
            text = await resp.aread()
            ...
        async for chunk in resp.aiter_bytes():
            ...
    """

    def __init__(
        self,
        session: AsyncSession,
        method: str,
        url: str,
        request_kwargs: dict[str, Any],
    ):
        """
        初始化流式上下文管理器。
        
        Args:
            session: curl-cffi 的 AsyncSession
            method: HTTP 方法
            url: 请求 URL
            request_kwargs: 请求参数字典
        """
        self._session = session
        self._method = method
        self._url = url
        self._request_kwargs = request_kwargs
        self._stream_context = None
        self._response: StreamResponse | None = None

    async def __aenter__(self) -> StreamResponse:
        """
        进入异步上下文管理器，发起流式请求。
        
        Returns:
            StreamResponse: 包装后的流式响应对象
        """
        try:
            normalized_kwargs = _normalize_http_version_in_kwargs(self._request_kwargs)
            self._stream_context = self._session.stream(
                self._method,
                self._url,
                **normalized_kwargs,
            )
            response = await self._stream_context.__aenter__()
        except CurlError as exc:
            code = getattr(exc, "code", None)
            if (
                code == CurlECode.HTTP2_STREAM
                and "http_version" not in self._request_kwargs
            ):
                logger.warning(
                    "curl-cffi HTTP/2 stream protocol error, retry stream with HTTP/1.1: url=%s",
                    self._url,
                )
                retry_kwargs = dict(self._request_kwargs)
                retry_kwargs["http_version"] = "1.1"
                try:
                    normalized_retry_kwargs = _normalize_http_version_in_kwargs(retry_kwargs)
                    self._stream_context = self._session.stream(
                        self._method,
                        self._url,
                        **normalized_retry_kwargs,
                    )
                    response = await self._stream_context.__aenter__()
                except CurlError as retry_exc:
                    raise httpx.HTTPError(str(retry_exc)) from retry_exc
            else:
                raise httpx.HTTPError(str(exc)) from exc

        self._response = StreamResponse(response)
        return self._response

    async def __aexit__(self, *args) -> None:
        """
        退出异步上下文管理器，关闭流式连接。
        
        Args:
            *args: 异常信息（如果有）
        """
        if self._stream_context:
            await self._stream_context.__aexit__(*args)
