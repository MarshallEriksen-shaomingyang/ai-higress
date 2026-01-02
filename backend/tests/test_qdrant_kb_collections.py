from __future__ import annotations

from uuid import UUID

import pytest

from app.settings import settings
from app.storage.qdrant_kb_collections import (
    get_kb_system_collection_name,
    get_kb_user_collection_name,
)


def test_get_kb_system_collection_name_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "qdrant_kb_system_collection", "kb_system_x", raising=False)
    assert get_kb_system_collection_name() == "kb_system_x"


def test_get_kb_user_collection_name_is_prefix_plus_user_hex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "per_user", raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_collection", "kb_user_x", raising=False)
    uid = UUID("00000000-0000-0000-0000-000000000001")
    assert get_kb_user_collection_name(uid) == "kb_user_x_00000000000000000000000000000001"


def test_get_kb_user_collection_name_accepts_str_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "per_user", raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_collection", "kb_user", raising=False)
    assert (
        get_kb_user_collection_name("00000000-0000-0000-0000-000000000001")
        == "kb_user_00000000000000000000000000000001"
    )


def test_get_kb_user_collection_name_sharded_by_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "sharded_by_model", raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_shards", 16, raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_collection", "kb_users", raising=False)
    uid = UUID("00000000-0000-0000-0000-000000000001")
    # sha1("embed-model-x")[:12] == d5bc9d262b9f
    assert get_kb_user_collection_name(uid, embedding_model="embed-model-x") == "kb_users_d5bc9d262b9f_shard_0001"


def test_get_kb_user_collection_name_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)
    monkeypatch.setattr(settings, "qdrant_kb_user_shared_collection", "kb_shared_v1", raising=False)
    uid = UUID("00000000-0000-0000-0000-000000000001")
    assert get_kb_user_collection_name(uid) == "kb_shared_v1"
