import pytest

from app.proxy_pool import ProxyPool, _parse_proxy_pool


def test_parse_proxy_pool_filters_invalid_entries():
    raw = "http://1.2.3.4:8080, socks5://5.6.7.8:1080, ftp://bad, not-a-url"
    proxies = _parse_proxy_pool(raw)
    assert proxies == ["http://1.2.3.4:8080", "socks5://5.6.7.8:1080"]


@pytest.mark.asyncio
async def test_proxy_pool_round_robin_picks_in_order():
    pool = ProxyPool(["http://a", "http://b"], strategy="round_robin")
    assert await pool.pick() == "http://a"
    assert await pool.pick() == "http://b"
    assert await pool.pick() == "http://a"


@pytest.mark.asyncio
async def test_proxy_pool_random_picks_from_pool():
    pool = ProxyPool(["http://a", "http://b"], strategy="random")
    picked = await pool.pick()
    assert picked in {"http://a", "http://b"}

