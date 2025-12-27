from __future__ import annotations

import pytest

from app.services import image_storage_service as svc


@pytest.mark.asyncio
async def test_presign_object_put_url_s3(monkeypatch):
    original_provider = svc.settings.image_storage_provider
    original_bucket = svc.settings.image_oss_bucket
    original_endpoint = svc.settings.image_oss_endpoint
    original_region = getattr(svc.settings, "image_oss_region", None)
    original_key_id = svc.settings.image_oss_access_key_id
    original_key_secret = svc.settings.image_oss_access_key_secret
    try:
        svc.settings.image_storage_provider = "s3"
        svc.settings.image_oss_bucket = "bucket"
        svc.settings.image_oss_endpoint = "https://r2.example.com"
        svc.settings.image_oss_region = "auto"
        svc.settings.image_oss_access_key_id = "ak"
        svc.settings.image_oss_access_key_secret = "sk"

        class DummyS3Client:
            def generate_presigned_url(self, ClientMethod: str, Params: dict, ExpiresIn: int):
                assert ClientMethod == "put_object"
                assert Params["Bucket"] == "bucket"
                assert Params["ContentType"] == "image/png"
                assert isinstance(Params["Key"], str)
                assert ExpiresIn == 123
                return "https://example.com/presigned-put"

        monkeypatch.setattr(svc, "_create_s3_client", lambda: DummyS3Client())

        result = await svc.presign_object_put_url(
            content_type="image/png",
            kind="videos",
            expires_seconds=123,
        )
        assert result.url == "https://example.com/presigned-put"
        assert result.headers["Content-Type"] == "image/png"
        assert result.expires_in == 123
        assert "videos/" in result.object_key
    finally:
        svc.settings.image_storage_provider = original_provider
        svc.settings.image_oss_bucket = original_bucket
        svc.settings.image_oss_endpoint = original_endpoint
        svc.settings.image_oss_region = original_region
        svc.settings.image_oss_access_key_id = original_key_id
        svc.settings.image_oss_access_key_secret = original_key_secret
