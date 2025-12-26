from __future__ import annotations

import time

from app.services.image_storage_service import build_signed_image_url


def test_media_images_endpoint_valid_signature_returns_bytes(client, monkeypatch):
    object_key = "generated-images/2025/01/01/abc.png"
    signed = build_signed_image_url(object_key, base_url="http://localhost:8000", ttl_seconds=3600)
    # signed is absolute; TestClient expects path.
    path = signed.replace("http://localhost:8000", "")

    async def _fake_load_image_bytes(key: str):
        assert key == object_key
        return b"PNGDATA", "image/png"

    monkeypatch.setattr("app.api.v1.media_routes.load_image_bytes", _fake_load_image_bytes)

    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("image/png")
    assert resp.content == b"PNGDATA"


def test_media_images_endpoint_expired_signature_returns_403(client):
    object_key = "generated-images/2025/01/01/abc.png"
    expires = int(time.time()) - 10
    # A dummy sig; should fail due to expiry first.
    resp = client.get(f"/media/images/{object_key}?expires={expires}&sig=deadbeef")
    assert resp.status_code == 403

