from __future__ import annotations

import uuid

import pytest

from app.services import audio_storage_service as svc


@pytest.mark.asyncio
async def test_store_and_load_audio_bytes_local(monkeypatch, tmp_path):
    original_mode = getattr(svc.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(svc.settings, "image_local_dir", None)
    original_prefix = getattr(svc.settings, "image_oss_prefix", "")
    try:
        svc.settings.image_storage_mode = "local"
        svc.settings.image_local_dir = str(tmp_path)
        svc.settings.image_oss_prefix = "generated-images"

        fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        monkeypatch.setattr(svc.uuid, "uuid4", lambda: fixed_uuid)
        monkeypatch.setattr(svc.time, "strftime", lambda *args, **kwargs: "2025/01/01")

        user_id = "00000000-0000-0000-0000-0000000000aa"
        raw = b"RIFF....WAVEfmt "  # fake wav header-ish

        stored = await svc.store_audio_bytes(
            raw,
            content_type="audio/wav",
            filename="input.wav",
            user_id=user_id,
        )

        expected_key = f"generated-images/user-audio/{user_id}/2025/01/01/{fixed_uuid.hex}.wav"
        assert stored.object_key == expected_key

        path = tmp_path / expected_key
        assert path.exists()

        loaded_bytes, loaded_type = await svc.load_audio_bytes(stored.object_key)
        assert loaded_bytes == raw
        assert isinstance(loaded_type, str)
        assert loaded_type
    finally:
        svc.settings.image_storage_mode = original_mode
        if original_local_dir is None:
            try:
                delattr(svc.settings, "image_local_dir")
            except Exception:
                pass
        else:
            svc.settings.image_local_dir = original_local_dir
        svc.settings.image_oss_prefix = original_prefix


@pytest.mark.asyncio
async def test_load_audio_bytes_local_rejects_traversal(monkeypatch, tmp_path):
    original_mode = getattr(svc.settings, "image_storage_mode", "auto")
    original_local_dir = getattr(svc.settings, "image_local_dir", None)
    try:
        svc.settings.image_storage_mode = "local"
        svc.settings.image_local_dir = str(tmp_path)

        with pytest.raises(ValueError):
            await svc.load_audio_bytes("generated-images/../secrets.txt")
    finally:
        svc.settings.image_storage_mode = original_mode
        if original_local_dir is None:
            try:
                delattr(svc.settings, "image_local_dir")
            except Exception:
                pass
        else:
            svc.settings.image_local_dir = original_local_dir

