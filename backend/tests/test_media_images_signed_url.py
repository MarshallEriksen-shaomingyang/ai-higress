from __future__ import annotations

import time

from app.services.image_storage_service import build_signed_image_url


def test_media_images_endpoint_valid_signature_returns_redirect(client, monkeypatch):
    object_key = "generated-images/2025/01/01/abc.png"
    signed = build_signed_image_url(object_key, base_url="http://localhost:8000", ttl_seconds=3600)
    # signed is absolute; TestClient expects path.
    path = signed.replace("http://localhost:8000", "")

    async def _fake_presign_image_get_url(key: str, *, expires_seconds: int):
        assert key == object_key
        assert 1 <= int(expires_seconds) <= 3600
        return "https://oss.example.com/presigned"

    monkeypatch.setattr(
        "app.api.v1.media_routes.presign_image_get_url",
        _fake_presign_image_get_url,
    )

    resp = client.get(path, allow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("location") == "https://oss.example.com/presigned"


def test_media_images_endpoint_expired_signature_returns_403(client):
    object_key = "generated-images/2025/01/01/abc.png"
    expires = int(time.time()) - 10
    # A dummy sig; should fail due to expiry first.
    resp = client.get(f"/media/images/{object_key}?expires={expires}&sig=deadbeef")
    assert resp.status_code == 403
