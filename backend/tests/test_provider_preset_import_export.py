from __future__ import annotations

from sqlalchemy import select

from app.models import ProviderPreset, User
from app.schemas import ProviderPresetCreateRequest
from app.services.provider_preset_service import create_provider_preset
from tests.utils import jwt_auth_headers


def _admin_headers(db_session):
    admin_user = db_session.execute(select(User)).scalars().first()
    assert admin_user is not None
    return jwt_auth_headers(str(admin_user.id))


def _seed_preset(db_session, preset_id: str, base_url: str = "https://api.example.com") -> ProviderPreset:
    return create_provider_preset(
        db_session,
        ProviderPresetCreateRequest(
            preset_id=preset_id,
            display_name=f"{preset_id}-name",
            base_url=base_url,
            provider_type="native",
            transport="http",
            models_path="/v1/models",
            chat_completions_path="/v1/chat/completions",
        ),
    )


def test_admin_can_export_presets(client, db_session):
    _seed_preset(db_session, "openai", "https://api.openai.com")
    _seed_preset(db_session, "claude", "https://api.anthropic.com")

    resp = client.get("/admin/provider-presets/export", headers=_admin_headers(db_session))
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2
    assert len(data["presets"]) == 2
    exported_ids = {item["preset_id"] for item in data["presets"]}
    assert exported_ids == {"openai", "claude"}

    first_item = data["presets"][0]
    assert "base_url" in first_item and "display_name" in first_item
    assert "id" not in first_item and "created_at" not in first_item


def test_import_presets_supports_skip_and_overwrite(client, db_session):
    existing = _seed_preset(db_session, "openai", "https://api.openai.com")

    # 不开启覆盖时应跳过已存在的预设
    skip_resp = client.post(
        "/admin/provider-presets/import",
        headers=_admin_headers(db_session),
        json={
            "overwrite": False,
            "presets": [
                {
                    "preset_id": "openai",
                    "display_name": "OpenAI Updated",
                    "description": "new desc",
                    "provider_type": "native",
                    "transport": "http",
                    "base_url": "https://api.new-openai.com",
                    "models_path": "/v1/models",
                    "messages_path": "/v1/message",
                    "chat_completions_path": "/v1/chat/completions",
                    "responses_path": None,
                    "supported_api_styles": ["openai"],
                    "retryable_status_codes": [429],
                    "custom_headers": {"X-Test": "1"},
                    "static_models": [],
                }
            ],
        },
    )
    assert skip_resp.status_code == 200
    skip_data = skip_resp.json()
    assert skip_data["skipped"] == ["openai"]
    assert skip_data["created"] == []
    assert skip_data["updated"] == []

    db_session.refresh(existing)
    assert existing.base_url.rstrip("/") == "https://api.openai.com"
    assert existing.base_url.startswith("https://api.openai.com")

    # 开启覆盖时应更新已有预设，并创建新的预设
    overwrite_resp = client.post(
        "/admin/provider-presets/import",
        headers=_admin_headers(db_session),
        json={
            "overwrite": True,
            "presets": [
                {
                    "preset_id": "openai",
                    "display_name": "OpenAI Updated",
                    "description": "updated via import",
                    "provider_type": "native",
                    "transport": "http",
                    "base_url": "https://api.overwrite-openai.com",
                    "models_path": "/v1/models",
                    "messages_path": "/v1/message",
                    "chat_completions_path": "/v1/chat/completions",
                    "responses_path": None,
                    "supported_api_styles": ["openai"],
                    "retryable_status_codes": [429, 500],
                    "custom_headers": {"X-Test": "2"},
                    "static_models": [{"id": "gpt-4o"}],
                },
                {
                    "preset_id": "claude",
                    "display_name": "Claude",
                    "provider_type": "native",
                    "transport": "http",
                    "base_url": "https://api.anthropic.com",
                    "models_path": "/v1/models",
                    "messages_path": "/v1/message",
                    "chat_completions_path": "/v1/chat/completions",
                    "responses_path": None,
                    "supported_api_styles": ["claude"],
                    "retryable_status_codes": [429],
                    "custom_headers": None,
                    "static_models": [],
                },
            ],
        },
    )
    assert overwrite_resp.status_code == 200
    overwrite_data = overwrite_resp.json()
    assert set(overwrite_data["updated"]) == {"openai"}
    assert set(overwrite_data["created"]) == {"claude"}
    assert overwrite_data["failed"] == []
    assert overwrite_data["skipped"] == []

    db_session.expire_all()
    updated = db_session.execute(
        select(ProviderPreset).where(ProviderPreset.preset_id == "openai")
    ).scalars().first()
    created = db_session.execute(
        select(ProviderPreset).where(ProviderPreset.preset_id == "claude")
    ).scalars().first()

    assert updated is not None
    assert updated.base_url.rstrip("/") == "https://api.overwrite-openai.com"
    assert updated.base_url.startswith("https://api.overwrite-openai.com")
    assert updated.description == "updated via import"
    assert created is not None
    assert created.display_name == "Claude"
