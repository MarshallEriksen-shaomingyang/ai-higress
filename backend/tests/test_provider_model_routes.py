from __future__ import annotations

from urllib.parse import quote

from sqlalchemy import select

from app.models import Provider, ProviderAPIKey, ProviderModel
from app.services.encryption import encrypt_secret
from tests.utils import jwt_auth_headers, seed_user_and_key


def _create_admin(session):
    admin, _ = seed_user_and_key(
        session,
        token_plain="model-admin-token",
        username="model-admin",
        email="model-admin@example.com",
        is_superuser=True,
    )
    return admin


def _create_provider(session, provider_slug: str) -> Provider:
    provider = Provider(
        provider_id=provider_slug,
        name=f"Provider {provider_slug}",
        base_url="https://models.example.com",
        provider_type="native",
        transport="http",
        visibility="public",
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


def test_admin_get_pricing_accepts_slash_model_id(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-pricing-slash")

    headers = jwt_auth_headers(str(admin.id))
    model_id = "provider-1/qwen3-32b"
    encoded_model_id = quote(model_id, safe="")

    resp = client.get(
        f"/admin/providers/{provider.provider_id}/models/{encoded_model_id}/pricing",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider.provider_id
    assert data["model_id"] == model_id
    assert data["pricing"] is None


def test_admin_update_pricing_accepts_slash_model_id(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-pricing-update-slash")

    headers = jwt_auth_headers(str(admin.id))
    model_id = "provider-2/qwen3-32b"
    encoded_model_id = quote(model_id, safe="")

    resp = client.put(
        f"/admin/providers/{provider.provider_id}/models/{encoded_model_id}/pricing",
        headers=headers,
        json={"input": 1.5, "output": 3.0},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_id"] == model_id
    assert data["pricing"] == {"input": 1.5, "output": 3.0}

    model_row = (
        db_session.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    assert model_row is not None
    assert model_row.pricing == {"input": 1.5, "output": 3.0}


def test_get_provider_model_mapping_accepts_slash_model_id(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-mapping-slash")

    model_id = "provider-3/qwen3-72b"
    model = ProviderModel(
        provider_id=provider.id,
        model_id=model_id,
        alias="qwen3-72b",
        family="qwen",
        display_name="qwen3-72b",
        context_length=8192,
        capabilities=["chat"],
        pricing=None,
        metadata_json=None,
        meta_hash=None,
    )
    db_session.add(model)
    db_session.commit()

    headers = jwt_auth_headers(str(admin.id))
    encoded_model_id = quote(model_id, safe="")
    resp = client.get(
        f"/providers/{provider.provider_id}/models/{encoded_model_id}/mapping",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_id"] == model_id
    assert data["alias"] == "qwen3-72b"


def test_update_provider_model_mapping_accepts_slash_model_id(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-mapping-update-slash")

    headers = jwt_auth_headers(str(admin.id))
    model_id = "provider-4/qwen3-120b"
    encoded_model_id = quote(model_id, safe="")

    resp = client.put(
        f"/providers/{provider.provider_id}/models/{encoded_model_id}/mapping",
        headers=headers,
        json={"alias": "qwen3-120b"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_id"] == model_id
    assert data["alias"] == "qwen3-120b"

    model_row = (
        db_session.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    assert model_row is not None
    assert model_row.alias == "qwen3-120b"


def test_update_provider_model_capabilities_accepts_slash_model_id(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-caps-update-slash")

    headers = jwt_auth_headers(str(admin.id))
    model_id = "provider-5/qwen3-235b"
    encoded_model_id = quote(model_id, safe="")

    # 预置聚合 /models 缓存，验证更新能力后会触发失效
    redis = client.app.state._test_redis
    assert redis is not None
    # MODELS_CACHE_KEY = "gateway:models:all"
    import asyncio
    asyncio.run(redis.set("gateway:models:all", "cached"))

    resp = client.put(
        f"/providers/{provider.provider_id}/models/{encoded_model_id}/capabilities",
        headers=headers,
        json={"capabilities": ["chat", "image_generation"]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_id"] == model_id
    assert sorted(data["capabilities"]) == ["chat", "image_generation"]

    model_row = (
        db_session.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    assert model_row is not None
    assert sorted(model_row.capabilities or []) == ["chat", "image_generation"]

    assert asyncio.run(redis.get("gateway:models:all")) is None


def test_provider_models_response_overlays_capabilities_override(client, db_session, monkeypatch):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-caps-overlay")

    # ProviderConfig 构建需要至少一个 active API key
    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()

    headers = jwt_auth_headers(str(admin.id))
    model_id = "chat-image-1"

    resp = client.put(
        f"/providers/{provider.provider_id}/models/{quote(model_id, safe='')}/capabilities",
        headers=headers,
        json={"capabilities": ["chat", "image_generation"]},
    )
    assert resp.status_code == 200

    async def _fake_models_cached(*args, **kwargs):
        return [
            {
                "model_id": model_id,
                "provider_id": provider.provider_id,
                "family": model_id,
                "display_name": model_id,
                "context_length": 8192,
                "capabilities": ["chat"],
                "pricing": None,
                "metadata": {"owned_by": "system"},
            }
        ]

    monkeypatch.setattr(
        "app.api.provider_routes.ensure_provider_models_cached", _fake_models_cached
    )

    resp = client.get(
        f"/providers/{provider.provider_id}/models",
        headers=headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    models = payload.get("models") or []
    assert models and models[0]["model_id"] == model_id
    # 覆盖生效：即使上游缓存里只有 chat，响应也应反映已配置的 image_generation
    assert "image_generation" in (models[0].get("capabilities") or [])


def test_get_provider_models_triggers_logical_model_sync_when_models_changed(
    client, db_session, monkeypatch
):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-tts-sync")

    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()

    async def _fake_models_cached(*args, **kwargs):
        return [
            {
                "model_id": "tts-1",
                "provider_id": provider.provider_id,
                "family": "tts",
                "display_name": "TTS 1",
                "context_length": 4096,
                "capabilities": ["audio"],
                "pricing": None,
                "metadata": {"owned_by": "system"},
            }
        ]

    calls: list[dict[str, object]] = []

    async def _fake_sync_logical_models(redis, *, session=None, provider_ids=None):
        calls.append({"provider_ids": list(provider_ids or [])})
        return []

    monkeypatch.setattr(
        "app.api.provider_routes.ensure_provider_models_cached", _fake_models_cached
    )
    monkeypatch.setattr(
        "app.services.logical_model_sync.sync_logical_models", _fake_sync_logical_models
    )

    headers = jwt_auth_headers(str(admin.id))

    resp_first = client.get(
        f"/providers/{provider.provider_id}/models",
        headers=headers,
    )
    assert resp_first.status_code == 200
    assert calls == [{"provider_ids": [provider.provider_id]}]

    # 第二次请求不应重复触发同步（provider_models 无变化）
    resp_second = client.get(
        f"/providers/{provider.provider_id}/models",
        headers=headers,
    )
    assert resp_second.status_code == 200
    assert calls == [{"provider_ids": [provider.provider_id]}]


def test_update_provider_model_tts_requirements_accepts_slash_model_id(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-tts-req-update-slash")

    headers = jwt_auth_headers(str(admin.id))
    model_id = "provider-tts/clone-model"
    encoded_model_id = quote(model_id, safe="")

    resp = client.put(
        f"/providers/{provider.provider_id}/models/{encoded_model_id}/tts-requirements",
        headers=headers,
        json={"requires_reference_audio": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider.provider_id
    assert data["model_id"] == model_id
    assert data["requires_reference_audio"] is True

    model_row = (
        db_session.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    assert model_row is not None
    meta = model_row.metadata_json
    assert isinstance(meta, dict)
    assert isinstance(meta.get("_gateway"), dict)
    assert isinstance(meta["_gateway"].get("tts"), dict)
    assert meta["_gateway"]["tts"].get("requires_reference_audio") is True


def test_update_provider_model_tts_requirements_preserves_existing_gateway_overrides(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_provider(db_session, "provider-tts-req-preserve")

    model_id = "tts-model-1"
    model = ProviderModel(
        provider_id=provider.id,
        model_id=model_id,
        alias=None,
        family="tts",
        display_name="tts-model-1",
        context_length=8192,
        capabilities=["audio"],
        pricing=None,
        metadata_json={"_gateway": {"capabilities_override": ["audio"]}, "upstream": {"owned_by": "system"}},
        meta_hash=None,
    )
    db_session.add(model)
    db_session.commit()

    headers = jwt_auth_headers(str(admin.id))
    resp = client.put(
        f"/providers/{provider.provider_id}/models/{quote(model_id, safe='')}/tts-requirements",
        headers=headers,
        json={"requires_reference_audio": True},
    )
    assert resp.status_code == 200

    # 注意：该更新发生在另一个 DB session 中；当前 db_session 可能持有旧对象缓存（expire_on_commit=False）。
    db_session.expire_all()

    model_row = (
        db_session.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_id == model_id,
            )
        )
        .scalars()
        .first()
    )
    assert model_row is not None
    meta = model_row.metadata_json
    assert isinstance(meta, dict)
    assert isinstance(meta.get("_gateway"), dict)
    assert meta["_gateway"].get("capabilities_override") == ["audio"]
    assert isinstance(meta["_gateway"].get("tts"), dict)
    assert meta["_gateway"]["tts"].get("requires_reference_audio") is True
