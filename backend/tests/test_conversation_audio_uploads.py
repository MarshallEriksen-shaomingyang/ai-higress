from __future__ import annotations

from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import APIKey, User
from app.services import audio_storage_service as storage


def test_upload_conversation_audio_and_playback_local(client: TestClient, db_session, tmp_path, monkeypatch):
    user = db_session.query(User).first()
    api_key = db_session.query(APIKey).first()
    assert user is not None
    assert api_key is not None

    # Override JWT auth dependency for assistant/conversation routes.
    client.app.dependency_overrides[require_jwt_token] = lambda: AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=bool(user.is_superuser),
        is_active=True,
    )

    original_mode = getattr(storage.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(storage.settings, "image_local_dir", None)
    original_prefix = getattr(storage.settings, "image_oss_prefix", "")
    try:
        storage.settings.image_storage_mode = "local"
        storage.settings.image_local_dir = str(tmp_path)
        storage.settings.image_oss_prefix = "generated-images"

        # Create assistant
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

        # Create conversation
        resp = client.post(
            "/v1/conversations",
            json={"assistant_id": assistant_id, "project_id": str(api_key.id), "title": "test"},
        )
        assert resp.status_code == 201
        conversation_id = resp.json()["conversation_id"]

        raw = b"RIFF....WAVEfmt "  # fake wav header-ish
        resp = client.post(
            f"/v1/conversations/{conversation_id}/audio-uploads",
            files={"file": ("input.wav", raw, "audio/wav")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body.get("audio_id"), str) and body["audio_id"]
        assert isinstance(body.get("object_key"), str) and body["object_key"]
        assert isinstance(body.get("url"), str) and body["url"]

        u = urlsplit(body["url"])
        path = u.path + (f"?{u.query}" if u.query else "")
        resp2 = client.get(path)
        assert resp2.status_code == 200
        assert resp2.content == raw
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
