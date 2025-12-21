"""
Session 管理器

负责：
- Session 绑定到 Provider
- Session 查询
- Session 上下文保存

这是对 app.routing.session_manager 的简单封装，提供更清晰的接口
"""

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = object  # type: ignore

from app.context_store import save_context
from app.logging_config import logger
from app.routing.session_manager import bind_session as routing_bind_session
from app.routing.session_manager import get_session as routing_get_session
from app.schemas import Session


class SessionManager:
    """Session 管理器，负责会话绑定和上下文保存"""

    def __init__(self, *, redis: Redis):
        self.redis = redis

    async def get_session(self, session_id: str) -> Session | None:
        """
        获取 Session
        
        Args:
            session_id: 会话 ID
        
        Returns:
            Session 对象，如果不存在则返回 None
        """
        return await routing_get_session(self.redis, session_id)

    async def bind_session(
        self,
        *,
        session_id: str,
        logical_model_id: str,
        provider_id: str,
        model_id: str,
    ) -> Session:
        """
        绑定 Session 到 Provider
        
        Args:
            session_id: 会话 ID
            logical_model_id: 逻辑模型 ID
            provider_id: Provider ID
            model_id: 模型 ID
        
        Returns:
            绑定后的 Session 对象
        """
        session = await routing_bind_session(
            self.redis,
            conversation_id=session_id,
            logical_model=logical_model_id,
            provider_id=provider_id,
            model_id=model_id,
        )

        logger.info(
            "📌 Session bound: session_id=%s logical_model=%s provider=%s model=%s",
            session_id,
            logical_model_id,
            provider_id,
            model_id,
        )

        return session

    async def save_context(
        self,
        *,
        session_id: str | None,
        request_payload: dict,
        response_text: str,
    ) -> None:
        """
        保存会话上下文
        
        Args:
            session_id: 会话 ID
            request_payload: 请求 payload
            response_text: 响应文本
        """
        if session_id:
            await save_context(self.redis, session_id, request_payload, response_text)
            logger.debug(
                "💾 Context saved: session_id=%s response_length=%d",
                session_id,
                len(response_text),
            )


__all__ = ["SessionManager"]
