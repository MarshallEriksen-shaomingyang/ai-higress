"""
测试 SessionManager 模块
"""

from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.chat.session_manager import SessionManager
from app.schemas import Session


@pytest.fixture
def mock_redis():
    """Mock Redis 客户端"""
    redis = MagicMock()
    return redis


@pytest.fixture
def session_manager(mock_redis):
    """创建 SessionManager 实例"""
    return SessionManager(redis=mock_redis)


@pytest.mark.asyncio
async def test_get_session_exists(session_manager, mock_redis):
    """测试获取存在的 Session"""
    from datetime import datetime

    # 准备测试数据
    now = datetime.now().timestamp()
    expected_session = Session(
        conversation_id="test-session-123",
        logical_model="gpt-4",
        provider_id="openai",
        model_id="gpt-4-turbo",
        created_at=now,
        last_accessed=now,
    )

    # Mock routing_get_session
    with patch("app.api.v1.chat.session_manager.routing_get_session") as mock_get:
        mock_get.return_value = expected_session

        # 执行测试
        result = await session_manager.get_session("test-session-123")

        # 验证结果
        assert result == expected_session
        mock_get.assert_called_once_with(mock_redis, "test-session-123")


@pytest.mark.asyncio
async def test_get_session_not_exists(session_manager, mock_redis):
    """测试获取不存在的 Session"""
    # Mock routing_get_session 返回 None
    with patch("app.api.v1.chat.session_manager.routing_get_session") as mock_get:
        mock_get.return_value = None

        # 执行测试
        result = await session_manager.get_session("non-existent-session")

        # 验证结果
        assert result is None
        mock_get.assert_called_once_with(mock_redis, "non-existent-session")


@pytest.mark.asyncio
async def test_bind_session(session_manager, mock_redis):
    """测试绑定 Session"""
    from datetime import datetime

    # 准备测试数据
    now = datetime.now().timestamp()
    expected_session = Session(
        conversation_id="test-session-456",
        logical_model="claude-3",
        provider_id="anthropic",
        model_id="claude-3-opus",
        created_at=now,
        last_accessed=now,
    )

    # Mock routing_bind_session
    with patch("app.api.v1.chat.session_manager.routing_bind_session") as mock_bind:
        mock_bind.return_value = expected_session

        # 执行测试
        result = await session_manager.bind_session(
            session_id="test-session-456",
            logical_model_id="claude-3",
            provider_id="anthropic",
            model_id="claude-3-opus",
        )

        # 验证结果
        assert result == expected_session
        mock_bind.assert_called_once_with(
            mock_redis,
            conversation_id="test-session-456",
            logical_model="claude-3",
            provider_id="anthropic",
            model_id="claude-3-opus",
        )


@pytest.mark.asyncio
async def test_save_context_with_session(session_manager, mock_redis):
    """测试保存会话上下文（有 session_id）"""
    # Mock save_context
    with patch("app.api.v1.chat.session_manager.save_context") as mock_save:
        mock_save.return_value = None

        # 执行测试
        await session_manager.save_context(
            session_id="test-session-789",
            request_payload={"messages": [{"role": "user", "content": "Hello"}]},
            response_text="Hi there!",
        )

        # 验证调用
        mock_save.assert_called_once_with(
            mock_redis,
            "test-session-789",
            {"messages": [{"role": "user", "content": "Hello"}]},
            "Hi there!",
        )


@pytest.mark.asyncio
async def test_save_context_without_session(session_manager, mock_redis):
    """测试保存会话上下文（无 session_id）"""
    # Mock save_context
    with patch("app.api.v1.chat.session_manager.save_context") as mock_save:
        mock_save.return_value = None

        # 执行测试
        await session_manager.save_context(
            session_id=None,
            request_payload={"messages": [{"role": "user", "content": "Hello"}]},
            response_text="Hi there!",
        )

        # 验证不调用 save_context
        mock_save.assert_not_called()
