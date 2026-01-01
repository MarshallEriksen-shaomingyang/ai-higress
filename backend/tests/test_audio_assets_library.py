from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import APIKey, User
from app.services.api_key_service import APIKeyExpiry, build_api_key_prefix, derive_api_key_hash
from app.services import audio_storage_service as storage


def _auth_as(client: TestClient, user: User):
    client.app.dependency_overrides[require_jwt_token] = lambda: AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=bool(user.is_superuser),
        is_active=True,
    )


def test_audio_assets_visibility_and_message_reference_by_audio_id(
    client: TestClient, db_session, tmp_path, monkeypatch
):
    # Seed users
    owner = db_session.query(User).first()
    api_key = db_session.query(APIKey).first()
    assert owner is not None
    assert api_key is not None

    other = User(
        username="u2",
        email="u2@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    other_api_key = APIKey(
        user_id=other.id,
        name="u2-key",
        key_hash=derive_api_key_hash("u2-token"),
        key_prefix=build_api_key_prefix("u2-token"),
        expiry_type=APIKeyExpiry.NEVER.value,
        expires_at=None,
        is_active=True,
        disabled_reason=None,
    )
    db_session.add(other_api_key)
    db_session.commit()
    db_session.refresh(other_api_key)

    original_mode = getattr(storage.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(storage.settings, "image_local_dir", None)
    original_prefix = getattr(storage.settings, "image_oss_prefix", "")
    try:
        storage.settings.image_storage_mode = "local"
        storage.settings.image_local_dir = str(tmp_path)
        storage.settings.image_oss_prefix = "generated-images"

        # Create assistant + conversation under owner
        _auth_as(client, owner)
        resp = client.post(
            "/v1/assistants",
            json={
                "project_id": str(api_key.id),
                "name": "默认助手",
                "system_prompt": "你是一个测试助手",
                "default_logical_model": "test-model",
            },
        )
        assert resp.status_code == 201
        assistant_id = resp.json()["assistant_id"]

        resp = client.post(
            "/v1/conversations",
            json={"assistant_id": assistant_id, "project_id": str(api_key.id), "title": "test"},
        )
        assert resp.status_code == 201
        conversation_id = resp.json()["conversation_id"]

        # Upload audio (private by default)
        raw = b"RIFF....WAVEfmt "
        resp = client.post(
            f"/v1/conversations/{conversation_id}/audio-uploads",
            files={"file": ("input.wav", raw, "audio/wav")},
        )
        assert resp.status_code == 201
        upload = resp.json()
        audio_id = upload["audio_id"]
        assert audio_id

        # Other user should not see private asset
        _auth_as(client, other)
        resp = client.get("/v1/audio-assets?visibility=all&limit=100")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(it.get("audio_id") != audio_id for it in items)

        # Owner shares it
        _auth_as(client, owner)
        resp = client.put(
            f"/v1/audio-assets/{audio_id}/visibility",
            json={"visibility": "public"},
        )
        assert resp.status_code == 200
        assert resp.json().get("visibility") == "public"

        # Other user can see public asset
        _auth_as(client, other)
        resp = client.get("/v1/audio-assets?visibility=all&limit=100")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(it.get("audio_id") == audio_id for it in items)

        # Patch non-stream executor to avoid real upstream and capture payload
        captured: dict = {}

        async def _stub_execute_run_non_stream(db, **kwargs):
            captured["payload_override"] = kwargs.get("payload_override")
            run = kwargs["run"]
            run.status = "succeeded"
            run.output_text = "ok"
            run.output_preview = "ok"
            run.response_payload = {"choices": [{"message": {"content": "ok"}}]}
            return run

        monkeypatch.setattr("app.services.chat_app_service.execute_run_non_stream", _stub_execute_run_non_stream)

        # Other user creates their own assistant + conversation, then references shared audio by audio_id
        _auth_as(client, other)
        resp = client.post(
            "/v1/assistants",
            json={
                "project_id": str(other_api_key.id),
                "name": "u2 assistant",
                "system_prompt": "test",
                "default_logical_model": "test-model",
            },
        )
        assert resp.status_code == 201
        other_assistant_id = resp.json()["assistant_id"]

        resp = client.post(
            "/v1/conversations",
            json={"assistant_id": other_assistant_id, "project_id": str(other_api_key.id), "title": "u2 conv"},
        )
        assert resp.status_code == 201
        other_conversation_id = resp.json()["conversation_id"]

        resp = client.post(
            f"/v1/conversations/{other_conversation_id}/messages",
            json={"content": "", "input_audio": {"audio_id": audio_id}, "streaming": False},
        )
        assert resp.status_code == 200, resp.text

        payload = captured.get("payload_override")
        assert isinstance(payload, dict)
        msgs = payload.get("messages")
        assert isinstance(msgs, list) and msgs
        last = msgs[-1]
        assert last.get("role") == "user"
        content = last.get("content")
        assert isinstance(content, list)
        assert any(
            isinstance(p, dict)
            and p.get("type") == "input_audio"
            and isinstance(p.get("input_audio"), dict)
            and isinstance(p["input_audio"].get("object_key"), str)
            for p in content
        )
    finally:
        storage.settings.image_storage_mode = original_mode
        if original_local_dir is None:
            try:
                delattr(storage.settings, "image_local_dir")
            except Exception:
                pass
        else:
            storage.settings.image_local_dir = original_local_dir
        storage.settings.image_oss_prefix = original_prefix
