import httpx
import pytest

from app.schemas import ProviderConfig, ProviderStatus
from app.provider.health import HealthStatus, check_provider_health
from app.provider.key_pool import reset_key_pool


def _make_provider() -> ProviderConfig:
    return ProviderConfig(
        id="mock",
        name="Mock Provider",
        base_url="https://api.mock.local",
        api_key="sk-test",  # pragma: allowlist secret
        models_path="/v1/models",
    )


@pytest.fixture(autouse=True)
def _reset_keys():
    reset_key_pool()
    yield
    reset_key_pool()


@pytest.mark.asyncio
async def test_check_provider_health_success():
    provider = _make_provider()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        status: HealthStatus = await check_provider_health(client, provider)

    assert status.provider_id == "mock"
    assert status.status == ProviderStatus.HEALTHY
    assert status.response_time_ms is not None
    assert status.error_message is None


@pytest.mark.asyncio
async def test_check_provider_health_server_error_marks_down():
    provider = _make_provider()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        status: HealthStatus = await check_provider_health(client, provider)

    assert status.status == ProviderStatus.DOWN
    assert status.error_message is not None


@pytest.mark.asyncio
async def test_check_provider_health_client_error_marks_degraded():
    provider = _make_provider()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limit"})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        status: HealthStatus = await check_provider_health(client, provider)

    assert status.status == ProviderStatus.DEGRADED
    assert status.error_message is not None
