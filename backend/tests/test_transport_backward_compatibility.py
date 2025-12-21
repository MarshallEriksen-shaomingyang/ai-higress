"""
向后兼容性测试：验证 transport 字段的添加不影响现有 Provider 行为

Requirements: 8.1, 8.3, 8.5
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Provider
from app.schemas.provider import TransportType


@pytest.fixture()
def session_factory():
    """创建内存数据库会话工厂"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    yield SessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_provider_default_transport_is_http(session_factory):
    """
    测试：创建 Provider 时，transport 字段默认为 'http'
    
    验证 Requirements 8.1, 8.3：
    - 现有 Provider 的 transport 字段为 http 时保持原有行为不变
    - 查询旧的 Provider 配置时，默认使用 http 传输模式
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建 Provider 时不指定 transport
        provider = Provider(
            provider_id="test-provider-default",
            name="Test Provider Default",
            base_url="https://api.example.com",
            provider_type="native",
            weight=1.0,
            status="healthy",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # 验证默认值为 'http'
        assert provider.transport == "http"
        assert provider.transport == TransportType.HTTP.value


def test_provider_explicit_http_transport(session_factory):
    """
    测试：显式设置 transport='http' 的 Provider 行为正常
    
    验证 Requirements 8.1：
    - 现有 Provider 的 transport 字段为 http 时保持原有行为不变
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 显式设置 transport='http'
        provider = Provider(
            provider_id="test-provider-http",
            name="Test Provider HTTP",
            base_url="https://api.example.com",
            transport="http",
            provider_type="native",
            weight=1.0,
            status="healthy",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # 验证 transport 为 'http'
        assert provider.transport == "http"
        assert provider.transport == TransportType.HTTP.value


def test_provider_sdk_transport_unchanged(session_factory):
    """
    测试：transport='sdk' 的 Provider 行为不受影响
    
    验证 Requirements 8.1：
    - 现有 Provider 的 transport 字段为 sdk 时保持原有行为不变
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建 transport='sdk' 的 Provider
        provider = Provider(
            provider_id="test-provider-sdk",
            name="Test Provider SDK",
            base_url="https://api.example.com",
            transport="sdk",
            sdk_vendor="openai",
            provider_type="native",
            weight=1.0,
            status="healthy",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # 验证 transport 为 'sdk'
        assert provider.transport == "sdk"
        assert provider.transport == TransportType.SDK.value
        assert provider.sdk_vendor == "openai"


def test_provider_claude_cli_transport_new_feature(session_factory):
    """
    测试：新增的 transport='claude_cli' 功能正常工作
    
    验证 Requirements 8.2：
    - 数据库迁移执行时，为 transport 字段添加 claude_cli 枚举值
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建 transport='claude_cli' 的 Provider
        provider = Provider(
            provider_id="test-provider-claude-cli",
            name="Test Provider Claude CLI",
            base_url="https://api.anthropic.com",
            transport="claude_cli",
            provider_type="native",
            weight=1.0,
            status="healthy",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # 验证 transport 为 'claude_cli'
        assert provider.transport == "claude_cli"
        assert provider.transport == TransportType.CLAUDE_CLI.value


def test_multiple_providers_with_different_transports(session_factory):
    """
    测试：多个 Provider 可以使用不同的 transport 类型共存
    
    验证 Requirements 8.1, 8.2, 8.3：
    - 不同 transport 类型的 Provider 可以共存
    - 每个 Provider 的 transport 设置独立
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建三个不同 transport 的 Provider
        providers = [
            Provider(
                provider_id="provider-http",
                name="HTTP Provider",
                base_url="https://api1.example.com",
                transport="http",
                provider_type="native",
                weight=1.0,
                status="healthy",
            ),
            Provider(
                provider_id="provider-sdk",
                name="SDK Provider",
                base_url="https://api2.example.com",
                transport="sdk",
                sdk_vendor="openai",
                provider_type="native",
                weight=1.0,
                status="healthy",
            ),
            Provider(
                provider_id="provider-claude-cli",
                name="Claude CLI Provider",
                base_url="https://api3.example.com",
                transport="claude_cli",
                provider_type="native",
                weight=1.0,
                status="healthy",
            ),
        ]

        for provider in providers:
            session.add(provider)
        session.commit()

        # 查询并验证每个 Provider 的 transport
        http_provider = session.query(Provider).filter_by(provider_id="provider-http").first()
        sdk_provider = session.query(Provider).filter_by(provider_id="provider-sdk").first()
        cli_provider = session.query(Provider).filter_by(provider_id="provider-claude-cli").first()

        assert http_provider.transport == "http"
        assert sdk_provider.transport == "sdk"
        assert cli_provider.transport == "claude_cli"


def test_provider_transport_field_in_api_response(session_factory):
    """
    测试：API 返回的 Provider 列表包含 transport 字段
    
    验证 Requirements 8.4：
    - API 返回 Provider 列表时，包含 transport 字段
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建一个 Provider
        provider = Provider(
            provider_id="test-provider-api",
            name="Test Provider API",
            base_url="https://api.example.com",
            transport="http",
            provider_type="native",
            weight=1.0,
            status="healthy",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # 验证 Provider 对象有 transport 属性
        assert hasattr(provider, "transport")
        assert provider.transport == "http"

        # 模拟 API 响应序列化
        from app.schemas.provider import ProviderResponse

        response = ProviderResponse.model_validate(provider)
        assert response.transport == "http"


def test_provider_update_transport_field(session_factory):
    """
    测试：可以更新 Provider 的 transport 字段
    
    验证：transport 字段可以被正常更新
    """
    SessionLocal = session_factory
    with SessionLocal() as session:
        # 创建一个默认 transport 的 Provider
        provider = Provider(
            provider_id="test-provider-update",
            name="Test Provider Update",
            base_url="https://api.example.com",
            provider_type="native",
            weight=1.0,
            status="healthy",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # 验证初始值
        assert provider.transport == "http"

        # 更新为 claude_cli
        provider.transport = "claude_cli"
        session.commit()
        session.refresh(provider)

        # 验证更新成功
        assert provider.transport == "claude_cli"

        # 再次更新为 sdk
        provider.transport = "sdk"
        provider.sdk_vendor = "openai"
        session.commit()
        session.refresh(provider)

        # 验证再次更新成功
        assert provider.transport == "sdk"
        assert provider.sdk_vendor == "openai"
