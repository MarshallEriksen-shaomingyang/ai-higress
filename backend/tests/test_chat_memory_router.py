from __future__ import annotations

from app.services.chat_memory_router import parse_memory_route_decision


def test_parse_memory_route_decision_empty() -> None:
    d = parse_memory_route_decision("")
    assert d.should_store is False
    assert d.scope == "none"
    assert d.memory_text == ""
    assert d.memory_items == []
    assert d.structured_ops == []


def test_parse_memory_route_decision_valid_user() -> None:
    d = parse_memory_route_decision('{"should_store": true, "scope": "user", "memory_text": "用户喜欢简洁回答"}')
    assert d.should_store is True
    assert d.scope == "user"
    assert d.memory_text == "用户喜欢简洁回答"
    assert d.structured_ops == []


def test_parse_memory_route_decision_prefers_items_joined_text() -> None:
    d = parse_memory_route_decision(
        '{"should_store": true, "scope": "user", "memory_text": "x", "memory_items": ['
        '{"content":"A","category":"preference","keywords":["k1"]},'
        '{"content":"B","category":"fact","keywords":["k2"]}'
        "]}"
    )
    assert d.should_store is True
    assert d.scope == "user"
    assert d.memory_text == "A\nB"
    assert len(d.memory_items) == 2
    assert d.structured_ops == []


def test_parse_memory_route_decision_rejects_missing_text() -> None:
    d = parse_memory_route_decision('{"should_store": true, "scope": "user", "memory_text": ""}')
    assert d.should_store is False
    assert d.scope == "none"


def test_parse_memory_route_decision_parses_structured_ops() -> None:
    d = parse_memory_route_decision(
        '{"should_store": true, "scope": "user", "memory_text": "A",'
        '"structured_ops":[{"op":"UPSERT","scope":"user","category":"preference","key":"response.style","value":"concise","confidence":0.8}]}'
    )
    assert d.should_store is True
    assert d.scope == "user"
    assert d.memory_text == "A"
    assert len(d.structured_ops) == 1
    assert d.structured_ops[0]["key"] == "response.style"
