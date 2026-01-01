from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models import APIKey, User
from app.services.chat_history_service import create_assistant, create_conversation, create_user_message
from app.services.tts_app_service import TTSAppService
from tests.utils import jwt_auth_headers


def test_audio_speech_requires_api_key(client):
    resp = client.post(
        "/v1/audio/speech",
        json={
            "model": "auto",
            "input": "hello",
            "voice": "alloy",
            "response_format": "mp3",
            "speed": 1.0,
        },
    )
    assert resp.status_code == 401


def test_audio_speech_upstream_failure_returns_http_error(client, api_key_auth_header, monkeypatch):
    async def _raise(self, request):  # type: ignore[no-untyped-def]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "upstream failed"},
        )

    monkeypatch.setattr(TTSAppService, "generate_speech_bytes", _raise, raising=True)

    resp = client.post(
        "/v1/audio/speech",
        json={
            "model": "auto",
            "input": "hello",
            "voice": "alloy",
            "response_format": "mp3",
            "speed": 1.0,
        },
        headers=api_key_auth_header,
    )
    assert resp.status_code == 503
    assert resp.json().get("detail", {}).get("message") == "upstream failed"


def test_message_speech_non_text_returns_400(client, db_session):
    user = db_session.execute(select(User).limit(1)).scalars().first()
    api_key = db_session.execute(select(APIKey).limit(1)).scalars().first()
    assert user is not None
    assert api_key is not None

    assistant = create_assistant(
        db_session,
        user_id=UUID(str(user.id)),
        project_id=UUID(str(api_key.id)),
        name="tts-test",
        system_prompt="",
        default_logical_model="auto",
        model_preset=None,
    )
    conversation = create_conversation(
        db_session,
        user_id=UUID(str(user.id)),
        project_id=UUID(str(api_key.id)),
        assistant_id=UUID(str(assistant.id)),
        title=None,
    )
    msg = create_user_message(db_session, conversation=conversation, content_text="hello")
    msg.content = {"type": "image_generation", "images": []}
    db_session.add(msg)
    db_session.commit()

    resp = client.post(
        f"/v1/messages/{UUID(str(msg.id))}/speech",
        json={"voice": "alloy", "speed": 1.0, "response_format": "mp3"},
        headers=jwt_auth_headers(str(user.id)),
    )
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Message is not plain text"


def test_message_speech_upstream_failure_returns_http_error(client, db_session, monkeypatch):
    async def _raise(self, request):  # type: ignore[no-untyped-def]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "upstream failed"},
        )

    monkeypatch.setattr(TTSAppService, "generate_speech_bytes", _raise, raising=True)

    user = db_session.execute(select(User).limit(1)).scalars().first()
    api_key = db_session.execute(select(APIKey).limit(1)).scalars().first()
    assert user is not None
    assert api_key is not None

    assistant = create_assistant(
        db_session,
        user_id=UUID(str(user.id)),
        project_id=UUID(str(api_key.id)),
        name="tts-test",
        system_prompt="",
        default_logical_model="auto",
        model_preset=None,
    )
    conversation = create_conversation(
        db_session,
        user_id=UUID(str(user.id)),
        project_id=UUID(str(api_key.id)),
        assistant_id=UUID(str(assistant.id)),
        title=None,
    )
    msg = create_user_message(db_session, conversation=conversation, content_text="hello")
    db_session.add(msg)
    db_session.commit()

    resp = client.post(
        f"/v1/messages/{UUID(str(msg.id))}/speech",
        json={"voice": "alloy", "speed": 1.0, "response_format": "mp3"},
        headers=jwt_auth_headers(str(user.id)),
    )
    assert resp.status_code == 503
    assert resp.json().get("detail", {}).get("message") == "upstream failed"
