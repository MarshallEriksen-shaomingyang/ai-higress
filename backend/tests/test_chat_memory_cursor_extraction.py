from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import sessionmaker

import app.tasks.chat_memory as chat_memory
from app.models import APIKey, AssistantPreset, Conversation, Message, User
from app.settings import settings


@dataclass(frozen=True)
class _Decision:
    should_store: bool
    scope: str
    memory_text: str
    memory_items: list[dict]


class _DummyAsyncClient:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_chat_memory_cursor_advances_on_no_memory(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    SessionLocal = sessionmaker(bind=db_session.get_bind(), future=True, expire_on_commit=False)
    monkeypatch.setattr(chat_memory, "SessionLocal", SessionLocal)

    # Enable Qdrant path but stub external deps.
    monkeypatch.setattr(chat_memory, "qdrant_is_configured", lambda: True)
    monkeypatch.setattr(chat_memory, "get_redis_client", lambda: object())
    monkeypatch.setattr(chat_memory, "get_qdrant_client", lambda: object())
    monkeypatch.setattr(chat_memory, "CurlCffiClient", lambda *a, **k: _DummyAsyncClient())
    monkeypatch.setattr(chat_memory, "get_or_default_project_eval_config", lambda *a, **k: object())
    monkeypatch.setattr(chat_memory, "get_effective_provider_ids_for_user", lambda *a, **k: set())
    monkeypatch.setattr(settings, "kb_global_embedding_logical_model", "embed-global", raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)

    calls: dict[str, str] = {}

    async def _fake_route(_db, *, transcript: str, **kwargs):
        calls["transcript"] = transcript
        return _Decision(should_store=False, scope="none", memory_text="", memory_items=[])

    monkeypatch.setattr(chat_memory, "route_chat_memory", _fake_route)

    user: User = db_session.query(User).first()
    api_key: APIKey = db_session.query(APIKey).first()
    assistant = AssistantPreset(
        id=uuid4(),
        user_id=user.id,
        api_key_id=api_key.id,
        name="a",
        system_prompt="",
        default_logical_model="gpt-4.1",
        title_logical_model=None,
        model_preset=None,
    )
    db_session.add(assistant)
    db_session.commit()

    conv = Conversation(
        id=uuid4(),
        user_id=user.id,
        api_key_id=api_key.id,
        assistant_id=assistant.id,
        title=None,
        last_activity_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=9999),
        archived_at=None,
        is_pinned=False,
        last_message_content=None,
        unread_count=0,
        summary_text="我们在做 Apollo 项目部署。",
        summary_until_sequence=0,
        summary_updated_at=None,
        last_memory_extracted_sequence=0,
    )
    db_session.add(conv)
    db_session.commit()

    m1 = Message(
        id=uuid4(),
        conversation_id=conv.id,
        role="user",
        content={"text": "记住我喜欢用 TypeScript。"},
        sequence=1,
    )
    m2 = Message(
        id=uuid4(),
        conversation_id=conv.id,
        role="assistant",
        content={"text": "好的。"},
        sequence=2,
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    out = await chat_memory.extract_and_store_chat_memory(
        conversation_id=UUID(str(conv.id)),
        user_id=UUID(str(user.id)),
        until_sequence=2,
    )
    assert out == "skipped:no_new_memory"

    db_session.refresh(conv)
    assert int(conv.last_memory_extracted_sequence) == 2
    assert "Conversation summary:" in calls.get("transcript", "")
    assert "New messages:" in calls.get("transcript", "")
    assert "user: 记住我喜欢用 TypeScript。" in calls.get("transcript", "")

    calls.clear()
    out2 = await chat_memory.extract_and_store_chat_memory(
        conversation_id=UUID(str(conv.id)),
        user_id=UUID(str(user.id)),
        until_sequence=2,
    )
    assert out2 == "skipped:no_new_messages"
    assert calls == {}


@pytest.mark.asyncio
async def test_chat_memory_batch_full_requeues_next_batch(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    SessionLocal = sessionmaker(bind=db_session.get_bind(), future=True, expire_on_commit=False)
    monkeypatch.setattr(chat_memory, "SessionLocal", SessionLocal)

    monkeypatch.setattr(chat_memory, "qdrant_is_configured", lambda: True)
    monkeypatch.setattr(chat_memory, "get_redis_client", lambda: object())
    monkeypatch.setattr(chat_memory, "get_qdrant_client", lambda: object())
    monkeypatch.setattr(chat_memory, "CurlCffiClient", lambda *a, **k: _DummyAsyncClient())
    monkeypatch.setattr(chat_memory, "get_or_default_project_eval_config", lambda *a, **k: object())
    monkeypatch.setattr(chat_memory, "get_effective_provider_ids_for_user", lambda *a, **k: set())
    monkeypatch.setattr(settings, "kb_global_embedding_logical_model", "embed-global", raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)

    # Force tiny batch size to trigger requeue behavior.
    monkeypatch.setattr(chat_memory, "_BATCH_LIMIT", 2)

    async def _fake_route(_db, *, transcript: str, **kwargs):
        _ = transcript
        return _Decision(should_store=False, scope="none", memory_text="", memory_items=[])

    monkeypatch.setattr(chat_memory, "route_chat_memory", _fake_route)

    enqueued: list[tuple[str, str, int]] = []

    def _fake_enqueue(*, conversation_id: UUID, user_id: UUID, until_sequence: int) -> None:
        enqueued.append((str(conversation_id), str(user_id), int(until_sequence)))

    monkeypatch.setattr(chat_memory, "_enqueue_next_batch_best_effort", _fake_enqueue)

    user: User = db_session.query(User).first()
    api_key: APIKey = db_session.query(APIKey).first()

    assistant = AssistantPreset(
        id=uuid4(),
        user_id=user.id,
        api_key_id=api_key.id,
        name="a2",
        system_prompt="",
        default_logical_model="gpt-4.1",
        title_logical_model=None,
        model_preset=None,
    )
    db_session.add(assistant)
    db_session.commit()

    conv = Conversation(
        id=uuid4(),
        user_id=user.id,
        api_key_id=api_key.id,
        assistant_id=assistant.id,
        title=None,
        last_activity_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=9999),
        archived_at=None,
        is_pinned=False,
        last_message_content=None,
        unread_count=0,
        summary_text="",
        summary_until_sequence=0,
        summary_updated_at=None,
        last_memory_extracted_sequence=0,
    )
    db_session.add(conv)
    db_session.commit()

    msgs = [
        Message(id=uuid4(), conversation_id=conv.id, role="user", content={"text": "m1"}, sequence=1),
        Message(id=uuid4(), conversation_id=conv.id, role="user", content={"text": "m2"}, sequence=2),
        Message(id=uuid4(), conversation_id=conv.id, role="user", content={"text": "m3"}, sequence=3),
    ]
    db_session.add_all(msgs)
    db_session.commit()

    out = await chat_memory.extract_and_store_chat_memory(
        conversation_id=UUID(str(conv.id)),
        user_id=UUID(str(user.id)),
        until_sequence=3,
    )
    assert out == "skipped:no_new_memory"

    db_session.refresh(conv)
    assert int(conv.last_memory_extracted_sequence) == 2
    assert enqueued == [(str(conv.id), str(user.id), 3)]
