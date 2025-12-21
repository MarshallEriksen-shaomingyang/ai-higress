import httpx
import pytest

from app.upstream import UpstreamStreamError, stream_upstream


@pytest.mark.asyncio
async def test_stream_upstream_wraps_open_http_error_as_upstream_stream_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(UpstreamStreamError) as excinfo:
            async for _ in stream_upstream(
                client=client,
                method="POST",
                url="https://example.invalid/v1/chat/completions",
                headers={},
                json_body={"model": "x", "messages": []},
                redis=None,
                session_id=None,
            ):
                pass

    assert excinfo.value.status_code is None
    assert "boom" in excinfo.value.text

