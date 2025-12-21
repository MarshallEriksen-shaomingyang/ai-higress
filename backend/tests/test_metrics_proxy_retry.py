import httpx
import pytest

from app.services.metrics_service import (
    call_upstream_http_with_metrics,
    stream_upstream_with_metrics,
)
from app.upstream import UpstreamStreamError


@pytest.mark.asyncio
async def test_call_upstream_http_retries_with_another_proxy_on_http_error(monkeypatch):
    # First proxy fails, second succeeds.
    async def fake_pick_upstream_proxy(*, exclude=None):
        exclude = exclude or set()
        return "http://good-proxy" if "http://bad-proxy" in exclude else "http://bad-proxy"

    monkeypatch.setattr(
        "app.services.metrics_service.pick_upstream_proxy",
        fake_pick_upstream_proxy,
        raising=True,
    )
    monkeypatch.setattr(
        "app.services.metrics_service.settings.upstream_proxy_max_retries",
        1,
        raising=False,
    )

    def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.metrics_service.record_provider_call_metric",
        _noop,
        raising=True,
    )

    used_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, timeout=None, proxy=None, **_kwargs):
            self.proxy = proxy

        async def __aenter__(self):
            used_proxies.append(self.proxy)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            if self.proxy == "http://bad-proxy":
                raise httpx.ConnectError("proxy down")
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        "app.services.metrics_service.httpx.AsyncClient",
        FakeAsyncClient,
        raising=True,
    )

    class DummyClient:
        timeout = 5.0

        async def post(self, *_args, **_kwargs):
            raise AssertionError("Should not fall back to direct client in this test")

    resp = await call_upstream_http_with_metrics(
        client=DummyClient(),
        url="https://example.invalid/v1/chat/completions",
        headers={},
        json_body={"model": "x"},
        db=None,  # record_provider_call_metric is patched
        provider_id="p",
        logical_model="m",
        user_id=None,
        api_key_id=None,
    )

    assert resp.status_code == 200
    assert used_proxies == ["http://bad-proxy", "http://good-proxy"]


@pytest.mark.asyncio
async def test_stream_upstream_retries_with_another_proxy_on_transport_upstream_stream_error(
    monkeypatch,
):
    async def fake_pick_upstream_proxy(*, exclude=None):
        exclude = exclude or set()
        return "http://good-proxy" if "http://bad-proxy" in exclude else "http://bad-proxy"

    monkeypatch.setattr(
        "app.services.metrics_service.pick_upstream_proxy",
        fake_pick_upstream_proxy,
        raising=True,
    )
    monkeypatch.setattr(
        "app.services.metrics_service.settings.upstream_proxy_max_retries",
        1,
        raising=False,
    )

    def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.metrics_service.record_provider_call_metric",
        _noop,
        raising=True,
    )

    used_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, timeout=None, proxy=None, **_kwargs):
            self.proxy = proxy

        async def __aenter__(self):
            used_proxies.append(self.proxy)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_stream_upstream(
        *,
        client,
        method: str,
        url: str,
        headers: dict,
        json_body: dict,
        redis,
        session_id: str | None,
        sse_style: str | None = None,
    ):
        if getattr(client, "proxy", None) == "http://bad-proxy":
            raise UpstreamStreamError(
                status_code=None,
                message="Upstream streaming transport error",
                text="proxy connect failed",
            )
        yield b"data: ok\n\n"

    monkeypatch.setattr(
        "app.services.metrics_service.httpx.AsyncClient",
        FakeAsyncClient,
        raising=True,
    )
    monkeypatch.setattr(
        "app.services.metrics_service.stream_upstream",
        fake_stream_upstream,
        raising=True,
    )

    class DummyClient:
        timeout = 5.0

    chunks: list[bytes] = []
    async for chunk in stream_upstream_with_metrics(
        client=DummyClient(),
        method="POST",
        url="https://example.invalid/v1/chat/completions",
        headers={},
        json_body={"model": "x"},
        redis=None,
        session_id=None,
        db=None,  # record_provider_call_metric is patched
        provider_id="p",
        logical_model="m",
        user_id=None,
        api_key_id=None,
    ):
        chunks.append(chunk)

    assert chunks == [b"data: ok\n\n"]
    assert used_proxies == ["http://bad-proxy", "http://good-proxy"]
