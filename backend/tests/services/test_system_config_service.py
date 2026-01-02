from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from uuid import uuid4

from app.models import SystemConfig
from app.services import system_config_service
from app.settings import settings


def test_get_effective_config_str_prefers_db(db_session):
    db_session.add(SystemConfig(key="X_TEST", value="db-value", value_type="string"))
    db_session.commit()

    cfg = system_config_service.get_effective_config_str(db_session, key="X_TEST")
    assert cfg.key == "X_TEST"
    assert cfg.value == "db-value"
    assert cfg.source == "db"


def test_get_effective_config_str_fallbacks_to_env_when_db_value_empty(db_session, monkeypatch):
    db_session.add(SystemConfig(key="X_TEST", value=None, value_type="string"))
    db_session.commit()

    monkeypatch.setenv("X_TEST", "env-value")
    cfg = system_config_service.get_effective_config_str(db_session, key="X_TEST")
    assert cfg.value == "env-value"
    assert cfg.source == "env"


@pytest.mark.asyncio
async def test_validate_kb_global_embedding_model_dimension_noop_when_not_shared(db_session, monkeypatch):
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "per_user", raising=False)
    out = await system_config_service.validate_kb_global_embedding_model_dimension(
        db_session,
        redis=object(),
        client=object(),
        current_user_id=uuid4(),
        current_username="admin",
        new_model="any",
    )
    assert out == 0


@pytest.mark.asyncio
async def test_validate_kb_global_embedding_model_dimension_rejects_when_qdrant_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)
    monkeypatch.setattr(system_config_service, "qdrant_is_configured", lambda: False)

    with pytest.raises(HTTPException) as exc:
        await system_config_service.validate_kb_global_embedding_model_dimension(
            db_session,
            redis=object(),
            client=object(),
            current_user_id=uuid4(),
            current_username="admin",
            new_model="embed-model",
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_validate_kb_global_embedding_model_dimension_includes_upstream_error_context(
    db_session, monkeypatch
):
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)
    monkeypatch.setattr(system_config_service, "qdrant_is_configured", lambda: True)
    monkeypatch.setattr(system_config_service, "_list_all_provider_ids", lambda _db: {"mock"})

    def _fake_exc():
        return HTTPException(
            status_code=502,
            detail=(
                "Upstream error provider=nvida-66849c86 upstream_status=400: "
                "Missing required parameter: input"
            ),
        )

    async def _fake_embed_text(*args, **kwargs):
        raise _fake_exc()

    monkeypatch.setattr(system_config_service, "embed_text", _fake_embed_text)

    with pytest.raises(HTTPException) as exc:
        await system_config_service.validate_kb_global_embedding_model_dimension(
            db_session,
            redis=object(),
            client=object(),
            current_user_id=uuid4(),
            current_username="admin",
            new_model="embed-model",
        )

    assert exc.value.status_code == 400
    assert "upstream_status=400" in str(exc.value.detail)
    assert "Missing required parameter: input" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_kb_global_embedding_model_dimension_rejects_on_dimension_mismatch(
    db_session, monkeypatch
):
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)
    monkeypatch.setattr(system_config_service, "qdrant_is_configured", lambda: True)
    monkeypatch.setattr(system_config_service, "_list_all_provider_ids", lambda _db: {"mock"})

    async def _fake_embed_text(*args, **kwargs):
        return [0.0, 0.0, 0.0, 0.0]

    async def _fake_get_collection_vector_size(*args, **kwargs):
        return 3

    async def _unexpected_ensure(*args, **kwargs):
        raise AssertionError("ensure_collection_vector_size should not be called on mismatch")

    class FakeQdrant:
        pass

    monkeypatch.setattr(system_config_service, "embed_text", _fake_embed_text)
    monkeypatch.setattr(system_config_service, "get_qdrant_client", lambda: FakeQdrant())
    monkeypatch.setattr(system_config_service, "get_collection_vector_size", _fake_get_collection_vector_size)
    monkeypatch.setattr(system_config_service, "ensure_collection_vector_size", _unexpected_ensure)

    with pytest.raises(HTTPException) as exc:
        await system_config_service.validate_kb_global_embedding_model_dimension(
            db_session,
            redis=object(),
            client=object(),
            current_user_id=uuid4(),
            current_username="admin",
            new_model="embed-model",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_validate_kb_global_embedding_model_dimension_creates_collection_when_missing(
    db_session, monkeypatch
):
    monkeypatch.setattr(settings, "qdrant_kb_user_collection_strategy", "shared", raising=False)
    monkeypatch.setattr(system_config_service, "qdrant_is_configured", lambda: True)
    monkeypatch.setattr(system_config_service, "_list_all_provider_ids", lambda _db: {"mock"})

    async def _fake_embed_text(*args, **kwargs):
        return [0.0] * 5

    async def _fake_get_collection_vector_size(*args, **kwargs):
        return None

    called: dict[str, int] = {}

    async def _fake_ensure_collection_vector_size(*args, **kwargs):
        called["vector_size"] = int(kwargs.get("vector_size"))
        return called["vector_size"]

    class FakeQdrant:
        pass

    monkeypatch.setattr(system_config_service, "embed_text", _fake_embed_text)
    monkeypatch.setattr(system_config_service, "get_qdrant_client", lambda: FakeQdrant())
    monkeypatch.setattr(system_config_service, "get_collection_vector_size", _fake_get_collection_vector_size)
    monkeypatch.setattr(system_config_service, "ensure_collection_vector_size", _fake_ensure_collection_vector_size)

    dim = await system_config_service.validate_kb_global_embedding_model_dimension(
        db_session,
        redis=object(),
        client=object(),
        current_user_id=uuid4(),
        current_username="admin",
        new_model="embed-model",
    )
    assert dim == 5
    assert called["vector_size"] == 5


def test_upsert_config_str_roundtrip(db_session):
    row = system_config_service.upsert_config_str(db_session, key="X_UPSERT", value="1", description="d")
    assert row.key == "X_UPSERT"

    cfg = system_config_service.get_effective_config_str(db_session, key="X_UPSERT")
    assert cfg.value == "1"
    assert cfg.source == "db"

    # Verify DB has exactly one row per key.
    count = db_session.execute(select(SystemConfig).where(SystemConfig.key == "X_UPSERT")).scalars().all()
    assert len(count) == 1
