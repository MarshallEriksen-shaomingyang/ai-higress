from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.v1.chat.request_handler import RequestHandler


@pytest.mark.asyncio
async def test_handle_stream_calls_provider_sink_with_model_id(monkeypatch):
    handler = RequestHandler(
        api_key=MagicMock(user_id="u", id="k", is_superuser=False),
        db=MagicMock(),
        redis=MagicMock(),
        client=MagicMock(),
    )

    async def _fake_try_candidates_stream(*, on_first_chunk, **kwargs):
        await on_first_chunk("p1", "m1")
        yield b"data: {}\n\n"

    monkeypatch.setattr(
        "app.api.v1.chat.request_handler.try_candidates_stream", _fake_try_candidates_stream
    )
    monkeypatch.setattr(
        "app.api.v1.chat.request_handler.record_provider_token_usage", lambda *args, **kwargs: None
    )

    selection = SimpleNamespace(ordered_candidates=[], base_weights={})

    called = {}

    def sink(provider_id: str, model_id: str) -> None:
        called["provider_id"] = provider_id
        called["model_id"] = model_id

    out = []
    async for chunk in handler.handle_stream(
        payload={"model": "x", "stream": True},
        requested_model="x",
        lookup_model_id="x",
        api_style="openai",
        effective_provider_ids=set(),
        selection=selection,
        session_id=None,
        idempotency_key="test",
        provider_id_sink=sink,
    ):
        out.append(chunk)
        break

    assert out
    assert called == {"provider_id": "p1", "model_id": "m1"}


@pytest.mark.asyncio
async def test_handle_stream_provider_sink_backwards_compat_one_arg(monkeypatch):
    handler = RequestHandler(
        api_key=MagicMock(user_id="u", id="k", is_superuser=False),
        db=MagicMock(),
        redis=MagicMock(),
        client=MagicMock(),
    )

    async def _fake_try_candidates_stream(*, on_first_chunk, **kwargs):
        await on_first_chunk("p2", "m2")
        yield b"data: {}\n\n"

    monkeypatch.setattr(
        "app.api.v1.chat.request_handler.try_candidates_stream", _fake_try_candidates_stream
    )
    monkeypatch.setattr(
        "app.api.v1.chat.request_handler.record_provider_token_usage", lambda *args, **kwargs: None
    )

    selection = SimpleNamespace(ordered_candidates=[], base_weights={})

    called = {}

    def sink(provider_id: str) -> None:
        called["provider_id"] = provider_id

    async for _chunk in handler.handle_stream(
        payload={"model": "x", "stream": True},
        requested_model="x",
        lookup_model_id="x",
        api_style="openai",
        effective_provider_ids=set(),
        selection=selection,
        session_id=None,
        idempotency_key="test",
        provider_id_sink=sink,
    ):
        break

    assert called == {"provider_id": "p2"}

