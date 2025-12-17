from __future__ import annotations

import httpx

from app.deps import get_http_client, get_redis
from app.models import Provider, ProviderAPIKey
from app.services.encryption import encrypt_secret
from tests.utils import InMemoryRedis, jwt_auth_headers, seed_user_and_key


def test_get_provider_models_returns_friendly_error_on_upstream_404(client, db_session):
    admin, _ = seed_user_and_key(
        db_session,
        token_plain="provider-models-404",
        username="provider-models-404",
        email="provider-models-404@example.com",
        is_superuser=True,
    )
    headers = jwt_auth_headers(str(admin.id))

    provider = Provider(
        provider_id="provider-models-upstream-404",
        name="Provider Upstream 404",
        base_url="https://upstream.example.com/openai",
        provider_type="native",
        transport="http",
        visibility="public",
        models_path="/v1/models",
    )
    db_session.add(provider)
    db_session.flush()

    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("sk-provider-models-404"),  # pragma: allowlist secret
            weight=1.0,
            max_qps=5,
            label="primary",
            status="active",
        )
    )
    db_session.commit()

    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/models"):
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(500, json={"error": "unexpected mock path"})

    async def override_get_http_client():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as http_client:
            yield http_client

    client.app.dependency_overrides[get_redis] = override_get_redis
    client.app.dependency_overrides[get_http_client] = override_get_http_client

    resp = client.get(f"/providers/{provider.provider_id}/models", headers=headers)
    assert resp.status_code == 502

    data = resp.json()
    assert data["detail"]["error"] == "provider_models_discovery_failed"
    assert data["detail"]["code"] == 502
    assert "无法获取该 Provider 的模型列表" in data["detail"]["message"]
    assert data["detail"]["details"]["provider_id"] == provider.provider_id
    assert data["detail"]["details"]["upstream_status_code"] == 404
    assert data["detail"]["details"]["upstream_url"].endswith("/v1/models")

