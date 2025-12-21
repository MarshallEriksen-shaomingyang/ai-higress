"""
CLI 配置路由测试
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_redis
from app.models import APIKey, User
from tests.utils import InMemoryRedis, jwt_auth_headers


def test_cli_install_endpoint_exists(client: TestClient):
    """测试 /api/v1/cli/install 端点存在"""
    response = client.get(
        "/api/v1/cli/install",
        params={
            "client": "claude",
            "platform": "mac",
            "key": "test-key-123456"
        }
    )
    # 应该返回 200 和脚本内容
    assert response.status_code == 200
    assert "#!/bin/bash" in response.text
    assert "Claude Code CLI" in response.text


def test_cli_install_command_endpoint_exists(client: TestClient):
    """测试 /api/v1/cli/install-command 端点存在"""
    response = client.get(
        "/api/v1/cli/install-command",
        params={
            "client": "claude",
            "platform": "mac",
            "key": "test-key-123456"
        }
    )
    # 应该返回 200 和 JSON 数据
    assert response.status_code == 200
    data = response.json()
    assert data["client"] == "claude"
    assert data["platform"] == "mac"
    assert "command" in data
    assert "script_url" in data


def test_cli_install_invalid_key(client: TestClient):
    """测试无效的 API Key"""
    response = client.get(
        "/api/v1/cli/install",
        params={
            "client": "claude",
            "platform": "mac",
            "key": "short"  # 太短的 key
        }
    )
    # 应该返回 400
    assert response.status_code == 400
    assert "无效的 API Key" in response.json()["detail"]


def test_cli_install_windows_platform(client: TestClient):
    """测试 Windows 平台脚本生成"""
    response = client.get(
        "/api/v1/cli/install",
        params={
            "client": "claude",
            "platform": "windows",
            "key": "test-key-123456"
        }
    )
    assert response.status_code == 200
    # Windows 使用 PowerShell
    assert "PowerShell" in response.text or "Write-Host" in response.text


def test_cli_install_codex_client(client: TestClient):
    """测试 Codex CLI 脚本生成"""
    response = client.get(
        "/api/v1/cli/install",
        params={
            "client": "codex",
            "platform": "linux",
            "key": "test-key-123456"
        }
    )
    assert response.status_code == 200
    assert "Codex CLI" in response.text
    assert "auth.json" in response.text
    assert "config.toml" in response.text


def test_cli_config_returns_prefix_and_url(
    client: TestClient,
    db_session: Session,
):
    """测试 /api/v1/cli/config/{api_key_id} 返回 key_prefix/api_url（不返回完整密钥）"""

    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    client.app.dependency_overrides[get_redis] = override_get_redis

    api_key = db_session.execute(select(APIKey)).scalars().first()
    assert api_key is not None
    user = db_session.get(User, api_key.user_id)
    assert user is not None

    resp = client.get(
        f"/api/v1/cli/config/{api_key.id}",
        headers=jwt_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["key_name"] == api_key.name
    assert data["key_prefix"] == api_key.key_prefix
    assert "api_url" in data
    assert "api_key" not in data
