from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import APIKey, User


def test_create_transcription_api_key_endpoint(client: TestClient, api_key_auth_header, monkeypatch):
    raw = b"RIFF....WAVEfmt "  # fake wav header-ish

    captured: dict[str, object] = {}

    class _FakeSTT:
        def __init__(self, *, client, redis, db, api_key):  # noqa: ANN001 - test stub
            _ = (client, redis, db, api_key)

        async def transcribe_bytes(
            self,
            *,
            model: str,
            audio_bytes: bytes,
            filename: str,
            content_type: str,
            language: str | None = None,
            prompt: str | None = None,
            request_id: str | None = None,
        ):
            captured["model"] = model
            captured["audio_bytes"] = audio_bytes
            captured["filename"] = filename
            captured["content_type"] = content_type
            captured["language"] = language
            captured["prompt"] = prompt
            captured["request_id"] = request_id
            return SimpleNamespace(text="你好")

    monkeypatch.setattr("app.api.v1.audio_routes.STTAppService", _FakeSTT)

    resp = client.post(
        "/v1/audio/transcriptions",
        headers=api_key_auth_header,
        data={"model": "stt-model", "language": "zh", "prompt": "please transcribe"},
        files={"file": ("input.wav", raw, "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"text": "你好"}
    assert captured["model"] == "stt-model"
    assert captured["audio_bytes"] == raw
    assert captured["filename"] == "input.wav"
    assert captured["content_type"] == "audio/wav"
    assert captured["language"] == "zh"
    assert captured["prompt"] == "please transcribe"


def test_conversation_audio_transcription_uses_assistant_default_model(client: TestClient, db_session, monkeypatch):
    user = db_session.query(User).first()
    api_key = db_session.query(APIKey).first()
    assert user is not None
    assert api_key is not None

    client.app.dependency_overrides[require_jwt_token] = lambda: AuthenticatedUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_superuser=bool(user.is_superuser),
        is_active=True,
    )

    captured: dict[str, object] = {}

    class _FakeSTT:
        def __init__(self, *, client, redis, db, api_key):  # noqa: ANN001 - test stub
            _ = (client, redis, db, api_key)

        async def transcribe_bytes(
            self,
            *,
            model: str,
            audio_bytes: bytes,
            filename: str,
            content_type: str,
            language: str | None = None,
            prompt: str | None = None,
            request_id: str | None = None,
        ):
            captured["model"] = model
            captured["audio_bytes"] = audio_bytes
            captured["filename"] = filename
            captured["content_type"] = content_type
            captured["language"] = language
            captured["prompt"] = prompt
            captured["request_id"] = request_id
            return SimpleNamespace(text="transcribed")

    monkeypatch.setattr("app.api.v1.assistant_routes.STTAppService", _FakeSTT)

    # Create assistant & conversation
    resp = client.post(
        "/v1/assistants",
        json={
            "project_id": str(api_key.id),
            "name": "默认助手",
            "system_prompt": "你是一个测试助手",
            "default_logical_model": "stt-default",
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

    raw = b"RIFF....WAVEfmt "  # fake wav header-ish
    resp = client.post(
        f"/v1/conversations/{conversation_id}/audio-transcriptions",
        data={"language": "zh"},
        files={"file": ("speech.wav", raw, "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"text": "transcribed"}
    assert captured["model"] == "stt-default"
    assert captured["audio_bytes"] == raw
    assert captured["language"] == "zh"

