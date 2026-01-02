from __future__ import annotations

from app.services.chat_memory_retrieval import (
    build_retrieval_query,
    inject_memory_context_into_messages,
    should_retrieve_user_memory,
)


def test_should_retrieve_user_memory_keyword() -> None:
    assert should_retrieve_user_memory("你还记得我上次说的偏好吗？") is True
    assert should_retrieve_user_memory("你好") is False


def test_build_retrieval_query_prepends_summary_when_short_or_pronoun() -> None:
    q = build_retrieval_query(user_text="它现在怎么样？", summary_text="我们在做 Apollo 项目部署。")
    assert "Conversation summary" in q
    assert "User query" in q


def test_inject_memory_context_into_messages_inserts_after_system() -> None:
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "system", "content": "summary"},
        {"role": "user", "content": "hi"},
    ]
    out = inject_memory_context_into_messages(msgs, memory_context="mem")
    assert out[0]["role"] == "system"
    assert out[1]["role"] == "system"
    assert out[2]["role"] == "system"
    assert out[2]["content"] == "mem"
    assert out[3]["role"] == "user"

