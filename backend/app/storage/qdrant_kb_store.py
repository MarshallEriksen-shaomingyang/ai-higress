from __future__ import annotations

from typing import Any

import httpx


QDRANT_DEFAULT_VECTOR_NAME = "text"


def _dig(obj: Any, *keys: str) -> Any:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


async def get_collection_vector_size(
    qdrant: httpx.AsyncClient, *, collection_name: str, vector_name: str = QDRANT_DEFAULT_VECTOR_NAME
) -> int | None:
    """
    Return vector size for the given collection, or None if it doesn't exist.
    """
    name = str(collection_name or "").strip()
    if not name:
        raise ValueError("empty collection_name")

    resp = await qdrant.get(f"/collections/{name}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    payload = resp.json()

    vectors = _dig(payload, "result", "config", "params", "vectors")
    size = None
    if isinstance(vectors, dict):
        # Named vectors: {"text": {"size": 1536, "distance": "Cosine"}}
        vn = str(vector_name or QDRANT_DEFAULT_VECTOR_NAME).strip() or QDRANT_DEFAULT_VECTOR_NAME
        size = _dig(vectors, vn, "size")
    else:
        # Single vector: {"size": 1536, "distance": "Cosine"}
        size = _dig(payload, "result", "config", "params", "vectors", "size")
    if isinstance(size, int) and size > 0:
        return size
    raise RuntimeError(f"unexpected qdrant collection response (missing vector size): {payload!r}")


async def create_collection(
    qdrant: httpx.AsyncClient,
    *,
    collection_name: str,
    vector_size: int,
    distance: str = "Cosine",
    vector_name: str = QDRANT_DEFAULT_VECTOR_NAME,
) -> None:
    name = str(collection_name or "").strip()
    if not name:
        raise ValueError("empty collection_name")
    size = int(vector_size)
    if size <= 0:
        raise ValueError("vector_size must be positive")

    vn = str(vector_name or QDRANT_DEFAULT_VECTOR_NAME).strip() or QDRANT_DEFAULT_VECTOR_NAME
    # Use named vectors to make the vector field explicit and stable.
    body = {"vectors": {vn: {"size": size, "distance": str(distance or "Cosine")}}}
    resp = await qdrant.put(f"/collections/{name}", json=body)
    resp.raise_for_status()


async def ensure_collection_vector_size(
    qdrant: httpx.AsyncClient,
    *,
    collection_name: str,
    vector_size: int,
    vector_name: str = QDRANT_DEFAULT_VECTOR_NAME,
) -> int:
    """
    Ensure the collection exists with the given vector size.

    If the collection exists but size mismatches, raise.
    """
    existing = await get_collection_vector_size(
        qdrant, collection_name=collection_name, vector_name=vector_name
    )
    expected = int(vector_size)
    if existing is not None:
        if existing != expected:
            raise RuntimeError(
                f"qdrant collection vector size mismatch: collection={collection_name} "
                f"existing={existing} expected={expected}"
            )
        return existing

    await create_collection(
        qdrant,
        collection_name=collection_name,
        vector_size=expected,
        distance="Cosine",
        vector_name=vector_name,
    )
    return expected


async def upsert_point(
    qdrant: httpx.AsyncClient,
    *,
    collection_name: str,
    point_id: str,
    vector: list[float],
    payload: dict[str, Any],
    wait: bool = True,
    vector_name: str = QDRANT_DEFAULT_VECTOR_NAME,
) -> None:
    name = str(collection_name or "").strip()
    if not name:
        raise ValueError("empty collection_name")
    pid = str(point_id or "").strip()
    if not pid:
        raise ValueError("empty point_id")
    if not isinstance(vector, list) or not vector:
        raise ValueError("empty vector")
    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")

    params = {"wait": "true" if wait else "false"}
    vn = str(vector_name or QDRANT_DEFAULT_VECTOR_NAME).strip() or QDRANT_DEFAULT_VECTOR_NAME
    body = {"points": [{"id": pid, "vector": {vn: vector}, "payload": payload}]}
    resp = await qdrant.put(f"/collections/{name}/points", params=params, json=body)
    resp.raise_for_status()


async def search_points(
    qdrant: httpx.AsyncClient,
    *,
    collection_name: str,
    vector: list[float],
    limit: int = 3,
    query_filter: dict[str, Any] | None = None,
    with_payload: bool = True,
    vector_name: str = QDRANT_DEFAULT_VECTOR_NAME,
) -> list[dict[str, Any]]:
    """
    Search points from Qdrant and return raw hit items (each includes payload/score/id).

    This is intentionally a thin wrapper around Qdrant REST:
    POST /collections/{collection}/points/search
    """
    name = str(collection_name or "").strip()
    if not name:
        raise ValueError("empty collection_name")
    if not isinstance(vector, list) or not vector:
        raise ValueError("empty vector")
    k = int(limit or 0)
    if k <= 0:
        k = 3
    k = max(1, min(k, 50))

    vn = str(vector_name or QDRANT_DEFAULT_VECTOR_NAME).strip() or QDRANT_DEFAULT_VECTOR_NAME
    body: dict[str, Any] = {
        "vector": {vn: vector},
        "limit": k,
        "with_payload": bool(with_payload),
    }
    if query_filter is not None:
        body["filter"] = query_filter

    resp = await qdrant.post(f"/collections/{name}/points/search", json=body)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("result")
    if isinstance(result, list):
        return [it for it in result if isinstance(it, dict)]
    return []


__all__ = [
    "QDRANT_DEFAULT_VECTOR_NAME",
    "create_collection",
    "ensure_collection_vector_size",
    "get_collection_vector_size",
    "search_points",
    "upsert_point",
]
