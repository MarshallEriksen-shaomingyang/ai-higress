from __future__ import annotations

import base64
import uuid

import pytest

from app.services import audio_input_service
from app.services import audio_storage_service as storage
from app.models import AudioAsset, User



@pytest.mark.asyncio
async def test_materialize_input_audio_in_payload_inlines_base64(monkeypatch, tmp_path):
    original_mode = getattr(storage.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(storage.settings, "image_local_dir", None)
    original_prefix = getattr(storage.settings, "image_oss_prefix", "")
    try:
        storage.settings.image_storage_mode = "local"
        storage.settings.image_local_dir = str(tmp_path)
        storage.settings.image_oss_prefix = "generated-images"

        fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000002")
        monkeypatch.setattr(storage.uuid, "uuid4", lambda: fixed_uuid)
        monkeypatch.setattr(storage.time, "strftime", lambda *args, **kwargs: "2025/01/01")

        user_id = "00000000-0000-0000-0000-0000000000bb"
        raw = b"fake-audio-bytes"
        stored = await storage.store_audio_bytes(
            raw,
            content_type="audio/mpeg",
            filename="input.mp3",
            user_id=user_id,
        )

        payload = {
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"object_key": stored.object_key, "format": "mp3"},
                        }
                    ],
                }
            ],
        }

        await audio_input_service.materialize_input_audio_in_payload(payload, user_id=user_id)
        part = payload["messages"][0]["content"][0]
        assert part["type"] == "input_audio"
        assert part["input_audio"]["format"] == "mp3"
        assert part["input_audio"]["data"] == base64.b64encode(raw).decode("ascii")
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


@pytest.mark.asyncio
async def test_materialize_input_audio_in_payload_rejects_wrong_user(monkeypatch, tmp_path):
    original_mode = getattr(storage.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(storage.settings, "image_local_dir", None)
    original_prefix = getattr(storage.settings, "image_oss_prefix", "")
    try:
        storage.settings.image_storage_mode = "local"
        storage.settings.image_local_dir = str(tmp_path)
        storage.settings.image_oss_prefix = "generated-images"

        fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000003")
        monkeypatch.setattr(storage.uuid, "uuid4", lambda: fixed_uuid)
        monkeypatch.setattr(storage.time, "strftime", lambda *args, **kwargs: "2025/01/01")

        owner_id = "00000000-0000-0000-0000-0000000000cc"
        stored = await storage.store_audio_bytes(
            b"fake",
            content_type="audio/wav",
            filename="input.wav",
            user_id=owner_id,
        )

        payload = {
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"object_key": stored.object_key}}
                    ],
                }
            ],
        }

        with pytest.raises(ValueError):
            await audio_input_service.materialize_input_audio_in_payload(payload, user_id="other-user")
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


@pytest.mark.asyncio
async def test_materialize_input_audio_in_payload_allows_public_shared_asset(monkeypatch, tmp_path, db_session):
    original_mode = getattr(storage.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(storage.settings, "image_local_dir", None)
    original_prefix = getattr(storage.settings, "image_oss_prefix", "")
    try:
        storage.settings.image_storage_mode = "local"
        storage.settings.image_local_dir = str(tmp_path)
        storage.settings.image_oss_prefix = "generated-images"

        owner = db_session.query(User).first()
        assert owner is not None

        shared_user = User(
            username="shared_u2",
            email="shared_u2@example.com",
            hashed_password="x",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(shared_user)
        db_session.commit()
        db_session.refresh(shared_user)

        fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000004")
        monkeypatch.setattr(storage.uuid, "uuid4", lambda: fixed_uuid)
        monkeypatch.setattr(storage.time, "strftime", lambda *args, **kwargs: "2025/01/01")

        stored = await storage.store_audio_bytes(
            b"fake-shared",
            content_type="audio/wav",
            filename="input.wav",
            user_id=str(owner.id),
        )
        asset = AudioAsset(
            owner_id=owner.id,
            conversation_id=None,
            object_key=stored.object_key,
            filename="input.wav",
            display_name="input.wav",
            content_type=stored.content_type,
            format="wav",
            size_bytes=stored.size_bytes,
            visibility="public",
        )
        db_session.add(asset)
        db_session.commit()

        payload = {
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"object_key": stored.object_key}}
                    ],
                }
            ],
        }
        await audio_input_service.materialize_input_audio_in_payload(
            payload,
            user_id=str(shared_user.id),
            db=db_session,
        )
        part = payload["messages"][0]["content"][0]
        assert isinstance(part.get("input_audio"), dict)
        assert isinstance(part["input_audio"].get("data"), str) and part["input_audio"]["data"]
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
