from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse

import app.services.embedding_service as embedding_service
from app.auth import AuthenticatedAPIKey
from typing import Any


@pytest.mark.asyncio
async def test_embed_text_sends_input_as_list(monkeypatch):
    captured: dict[str, object] = {}

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

    api_key = AuthenticatedAPIKey(
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
