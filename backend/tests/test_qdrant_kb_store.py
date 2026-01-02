from __future__ import annotations

import httpx
import pytest

from app.storage.qdrant_kb_store import (
    QDRANT_DEFAULT_VECTOR_NAME,
    ensure_collection_vector_size,
    get_collection_vector_size,
    search_points,
)


@pytest.mark.asyncio
async def test_get_collection_vector_size_none_on_404() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/collections/kb_user_x"
        return httpx.Response(404, json={"status": "not_found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://qdrant:6333", transport=transport) as client:
        assert await get_collection_vector_size(client, collection_name="kb_user_x") is None


@pytest.mark.asyncio
async def test_ensure_collection_vector_size_creates_when_missing() -> None:
    calls: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/collections/kb_user_x":
            return httpx.Response(404, json={"status": "not_found"})
        if request.method == "PUT" and request.url.path == "/collections/kb_user_x":
            body = request.json()
            assert body["vectors"][QDRANT_DEFAULT_VECTOR_NAME]["size"] == 1536
            assert str(body["vectors"][QDRANT_DEFAULT_VECTOR_NAME]["distance"]).lower() == "cosine"
            return httpx.Response(200, json={"result": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://qdrant:6333", transport=transport) as client:
        size = await ensure_collection_vector_size(client, collection_name="kb_user_x", vector_size=1536)
        assert size == 1536
        assert calls == [("GET", "/collections/kb_user_x"), ("PUT", "/collections/kb_user_x")]


@pytest.mark.asyncio
async def test_ensure_collection_vector_size_raises_on_mismatch() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/collections/kb_user_x":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "config": {
                            "params": {
                                "vectors": {QDRANT_DEFAULT_VECTOR_NAME: {"size": 1024, "distance": "Cosine"}}
                            }
                        }
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://qdrant:6333", transport=transport) as client:
        with pytest.raises(RuntimeError, match="vector size mismatch"):
            await ensure_collection_vector_size(client, collection_name="kb_user_x", vector_size=1536)


@pytest.mark.asyncio
async def test_search_points_sends_named_vector_and_filter() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/collections/kb_shared_v1/points/search"
        body = request.json()
        assert body["vector"][QDRANT_DEFAULT_VECTOR_NAME] == [0.1, 0.2, 0.3]
        assert body["limit"] == 3
        assert body["with_payload"] is True
        assert body["filter"]["must"][0]["key"] == "owner_user_id"
        return httpx.Response(
            200,
            json={
                "result": [
                    {"id": "p1", "score": 0.9, "payload": {"text": "hello"}},
                    {"id": "p2", "score": 0.8, "payload": {"text": "world"}},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://qdrant:6333", transport=transport) as client:
        hits = await search_points(
            client,
            collection_name="kb_shared_v1",
            vector=[0.1, 0.2, 0.3],
            limit=3,
            query_filter={"must": [{"key": "owner_user_id", "match": {"value": "u1"}}]},
        )
        assert len(hits) == 2
        assert hits[0]["payload"]["text"] == "hello"
