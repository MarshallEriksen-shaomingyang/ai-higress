from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse

import app.services.embedding_service as embedding_service
from app.auth import AuthenticatedAPIKey
from typing import Any


def _make_api_key() -> AuthenticatedAPIKey:
    return AuthenticatedAPIKey(
        id=uuid4(),
        user_id=uuid4(),
        user_username="admin",
        is_superuser=True,
        name="test",
        is_active=True,
        disabled_reason=None,
        has_provider_restrictions=False,
        allowed_provider_ids=[],
    )


def _patch_handler(monkeypatch: Any, captured: dict[str, object]) -> None:
    class FakeHandler:
        def __init__(self, *, api_key: Any, db: Any, redis: Any, client: Any):
            self.api_key = api_key
            self.db = db
            self.redis = redis
            self.client = client

        async def handle(self, *, payload: dict[str, Any], **kwargs: Any):
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            return JSONResponse(content={"data": [{"embedding": [1.0, 2.0]}]})

    monkeypatch.setattr(embedding_service, "RequestHandler", FakeHandler)


@pytest.mark.asyncio
async def test_embed_text_sends_input_as_list(monkeypatch):
    captured: dict[str, object] = {}

    _patch_handler(monkeypatch, captured)
    api_key = _make_api_key()

    vec = await embedding_service.embed_text(
        db=object(),
        redis=object(),
        client=object(),
        api_key=api_key,
        effective_provider_ids={"mock"},
        embedding_logical_model="embed-model",
        text="  hello  ",
        idempotency_key="k",
    )

    assert vec == [1.0, 2.0]
    assert captured["payload"] == {"model": "embed-model", "input": ["hello"]}


@pytest.mark.asyncio
async def test_embed_text_defaults_input_type_for_asymmetric_models(monkeypatch):
    captured: dict[str, object] = {}
    _patch_handler(monkeypatch, captured)

    api_key = _make_api_key()
    await embedding_service.embed_text(
        db=object(),
        redis=object(),
        client=object(),
        api_key=api_key,
        effective_provider_ids={"mock"},
        embedding_logical_model="embed-multilingual-v3.0",
        text="hello",
        idempotency_key="k",
    )

    assert captured["payload"]["input_type"] == "search_document"


@pytest.mark.asyncio
async def test_embed_text_respects_explicit_input_type(monkeypatch):
    captured: dict[str, object] = {}
    _patch_handler(monkeypatch, captured)

    api_key = _make_api_key()
    await embedding_service.embed_text(
        db=object(),
        redis=object(),
        client=object(),
        api_key=api_key,
        effective_provider_ids={"mock"},
        embedding_logical_model="embed-english-v3.0",
        text="hello",
        idempotency_key="k",
        input_type="search_query",
    )

    assert captured["payload"]["input_type"] == "search_query"


@pytest.mark.asyncio
async def test_embed_text_omits_input_type_for_openai_models(monkeypatch):
    captured: dict[str, object] = {}
    _patch_handler(monkeypatch, captured)

    api_key = _make_api_key()
    await embedding_service.embed_text(
        db=object(),
        redis=object(),
        client=object(),
        api_key=api_key,
        effective_provider_ids={"mock"},
        embedding_logical_model="text-embedding-3-small",
        text="hello",
        idempotency_key="k",
        input_type="search_query",
    )

    assert "input_type" not in captured["payload"]
