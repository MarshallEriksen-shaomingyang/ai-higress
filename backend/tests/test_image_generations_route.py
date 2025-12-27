from __future__ import annotations

import httpx
import pytest

from app.models import Provider, ProviderAPIKey
from app.services.encryption import encrypt_secret


def _seed_provider_with_image_model(
    db_session, *, provider_id: str, model_id: str, base_url: str = "https://upstream.example.com"
) -> None:
    provider = Provider(
        provider_id=provider_id,
        name="Image Provider",
        base_url=base_url,
        transport="http",
        chat_completions_path="/v1/chat/completions",
        images_generations_path="/v1/images/generations",
        static_models=[
            {
                "id": model_id,
                "display_name": model_id,
                "family": model_id,
                "context_length": 8192,
                "capabilities": ["image_generation"],
            }
        ],
    )
    db_session.add(provider)
    db_session.flush()

    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()


def test_images_generations_requires_api_key(client):
    resp = client.post(
        "/v1/images/generations",
        json={"prompt": "a cat", "model": "gpt-image-1"},
    )
    assert resp.status_code == 401


def test_images_generations_openai_lane_happy_path(client, db_session, monkeypatch, api_key_auth_header):
    _seed_provider_with_image_model(db_session, provider_id="openai-like", model_id="gpt-image-1")

    seen: dict[str, object] = {}

    async def _fake_call(**kwargs):
        seen["url"] = kwargs.get("url")
        seen["json_body"] = kwargs.get("json_body")
        return httpx.Response(
            200,
            json={
                "created": 1700000000,
                "data": [{"b64_json": "AAAB", "revised_prompt": "a cat"}],
                "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            },
        )

    monkeypatch.setattr(
        "app.services.image_app_service.call_upstream_http_with_metrics", _fake_call
    )

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={
            "prompt": "a cat",
            "model": "gpt-image-1",
            "n": 1,
            "response_format": "b64_json",
            "size": "1024x1024",
            "extra_body": {"openai": {"size": "512x512"}},
        },
    )
    assert resp.status_code == 200, resp.text
    assert seen["url"] == "https://upstream.example.com/v1/images/generations"
    assert isinstance(seen["json_body"], dict)
    assert "extra_body" not in seen["json_body"]
    assert seen["json_body"]["size"] == "512x512"
    payload = resp.json()
    assert payload["created"] == 1700000000
    assert payload["data"][0]["b64_json"] == "AAAB"


def test_images_generations_omits_response_format_when_null(
    client, db_session, monkeypatch, api_key_auth_header
):
    _seed_provider_with_image_model(db_session, provider_id="openai-like", model_id="gpt-image-1")

    seen: dict[str, object] = {}

    async def _fake_call(**kwargs):
        seen["json_body"] = kwargs.get("json_body")
        return httpx.Response(
            200,
            json={
                "created": 1700000000,
                "data": [{"b64_json": "AAAB", "revised_prompt": "a cat"}],
            },
        )

    monkeypatch.setattr(
        "app.services.image_app_service.call_upstream_http_with_metrics", _fake_call
    )

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={
            "prompt": "a cat",
            "model": "gpt-image-1",
            "n": 1,
            "response_format": None,
        },
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(seen.get("json_body"), dict)
    assert "response_format" not in seen["json_body"]
    payload = resp.json()
    assert payload["data"][0]["b64_json"] == "AAAB"


def test_images_generations_chat_completions_compat_payload_shape(
    client, db_session, monkeypatch, api_key_auth_header
):
    provider_id = "openai-chat-images"
    model_id = "chat-image-1"
    provider = Provider(
        provider_id=provider_id,
        name="Chat Images Provider",
        base_url="https://upstream.example.com",
        transport="http",
        chat_completions_path="/v1/chat/completions",
        # Non-standard: provider expects chat payload for image generation.
        images_generations_path="/v1/chat/completions",
        static_models=[
            {
                "id": model_id,
                "display_name": model_id,
                "family": model_id,
                "context_length": 8192,
                "capabilities": ["image_generation"],
            }
        ],
    )
    db_session.add(provider)
    db_session.flush()
    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()

    seen: dict[str, object] = {}

    async def _fake_call(**kwargs):
        seen["url"] = kwargs.get("url")
        seen["json_body"] = kwargs.get("json_body")
        return httpx.Response(
            200,
            json={
                "created": 1700000000,
                "data": [{"b64_json": "AAAB", "revised_prompt": "a cat"}],
            },
        )

    monkeypatch.setattr("app.services.image_app_service.call_upstream_http_with_metrics", _fake_call)

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={
            "prompt": "a cat",
            "model": model_id,
            "n": 1,
            "size": "1024x1024",
        },
    )
    assert resp.status_code == 200
    assert seen["url"] == "https://upstream.example.com/v1/chat/completions"
    assert isinstance(seen["json_body"], dict)
    assert "messages" in seen["json_body"]
    assert "prompt" not in seen["json_body"]
    assert seen["json_body"]["messages"][0]["role"] == "user"


def test_images_generations_chat_completions_compat_response_shape(
    client, db_session, monkeypatch, api_key_auth_header
):
    provider_id = "openai-chat-images"
    model_id = "chat-image-1"
    provider = Provider(
        provider_id=provider_id,
        name="Chat Images Provider",
        base_url="https://upstream.example.com",
        transport="http",
        chat_completions_path="/v1/chat/completions",
        images_generations_path="/v1/chat/completions",
        static_models=[
            {
                "id": model_id,
                "display_name": model_id,
                "family": model_id,
                "context_length": 8192,
                "capabilities": ["image_generation"],
            }
        ],
    )
    db_session.add(provider)
    db_session.flush()
    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()

    image_url = "https://cdn.example.com/generated.png"

    async def _fake_call(**kwargs):
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-abc",
                "object": "chat.completion",
                "created": 1700000000,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": f"Here: {image_url}"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )

    monkeypatch.setattr("app.services.image_app_service.call_upstream_http_with_metrics", _fake_call)

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={"prompt": "a cat", "model": model_id, "n": 1, "response_format": "url"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert isinstance(payload.get("data"), list) and payload["data"]
    assert payload["data"][0]["url"] == image_url


def test_images_generations_chat_completions_compat_response_data_url(
    client, db_session, monkeypatch, api_key_auth_header
):
    provider_id = "openai-chat-images"
    model_id = "chat-image-1"
    provider = Provider(
        provider_id=provider_id,
        name="Chat Images Provider",
        base_url="https://upstream.example.com",
        transport="http",
        chat_completions_path="/v1/chat/completions",
        images_generations_path="/v1/chat/completions",
        static_models=[
            {
                "id": model_id,
                "display_name": model_id,
                "family": model_id,
                "context_length": 8192,
                "capabilities": ["image_generation"],
            }
        ],
    )
    db_session.add(provider)
    db_session.flush()
    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()

    data_url = "data:image/png;base64,AAAB"

    async def _fake_call(**kwargs):
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-abc",
                "object": "chat.completion",
                "created": 1700000000,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": f"ok {data_url}"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    monkeypatch.setattr("app.services.image_app_service.call_upstream_http_with_metrics", _fake_call)

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={"prompt": "a cat", "model": model_id, "n": 1, "response_format": "b64_json"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data"][0]["b64_json"] == "AAAB"


def test_images_generations_chat_completions_compat_response_message_images_field(
    client, db_session, monkeypatch, api_key_auth_header
):
    provider_id = "openai-chat-images"
    model_id = "chat-image-1"
    provider = Provider(
        provider_id=provider_id,
        name="Chat Images Provider",
        base_url="https://upstream.example.com",
        transport="http",
        chat_completions_path="/v1/chat/completions",
        images_generations_path="/v1/chat/completions",
        static_models=[
            {
                "id": model_id,
                "display_name": model_id,
                "family": model_id,
                "context_length": 8192,
                "capabilities": ["image_generation"],
            }
        ],
    )
    db_session.add(provider)
    db_session.flush()
    db_session.add(
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("upstream-key"),
            weight=1.0,
            status="active",
        )
    )
    db_session.commit()

    image_url = "https://cdn.example.com/generated.png"

    async def _fake_call(**kwargs):
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-abc",
                "object": "chat.completion",
                "created": 1700000000,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "images": [{"url": image_url}]},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    monkeypatch.setattr("app.services.image_app_service.call_upstream_http_with_metrics", _fake_call)

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={"prompt": "a cat", "model": model_id, "n": 1, "response_format": "url"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data"][0]["url"] == image_url


@pytest.mark.parametrize(
    "model_id",
    ["gemini-2.5-flash-image", "gemini-3-pro-image-preview", "nano-banana"],
)
def test_images_generations_google_lane_happy_path(client, db_session, monkeypatch, api_key_auth_header, model_id: str):
    _seed_provider_with_image_model(
        db_session,
        provider_id="google-like",
        model_id=model_id,
        base_url="https://generativelanguage.googleapis.com",
    )

    seen: dict[str, object] = {}

    async def _fake_call(**kwargs):
        seen["url"] = kwargs.get("url")
        seen["json_body"] = kwargs.get("json_body")
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": "AAAC",
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "app.services.image_app_service.call_upstream_http_with_metrics", _fake_call
    )

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={
            "prompt": "a cat",
            "model": model_id,
            "n": 1,
            "response_format": "b64_json",
            "extra_body": {"google": {"generationConfig": {"imageConfig": {"aspectRatio": "16:9"}}}},
        },
    )
    assert resp.status_code == 200
    assert isinstance(seen.get("url"), str) and "/v1beta/models/" in seen["url"]
    assert str(seen["url"]).endswith(":generateContent")
    assert isinstance(seen.get("json_body"), dict)
    assert seen["json_body"]["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
    payload = resp.json()
    assert payload["data"][0]["b64_json"] == "AAAC"


def test_images_generations_google_imagen_predict_happy_path(client, db_session, monkeypatch, api_key_auth_header):
    _seed_provider_with_image_model(
        db_session,
        provider_id="google-like",
        model_id="imagen-4.0-generate-001",
        base_url="https://generativelanguage.googleapis.com",
    )

    seen: dict[str, object] = {}

    async def _fake_call(**kwargs):
        seen["url"] = kwargs.get("url")
        seen["json_body"] = kwargs.get("json_body")
        return httpx.Response(
            200,
            json={
                "predictions": [
                    {
                        "mimeType": "image/png",
                        "bytesBase64Encoded": "AAAD",
                        "prompt": "enhanced prompt",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "app.services.image_app_service.call_upstream_http_with_metrics", _fake_call
    )

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={
            "prompt": "a cat",
            "model": "imagen-4.0-generate-001",
            "n": 1,
            "size": "1792x1024",
            "response_format": "b64_json",
        },
    )
    assert resp.status_code == 200
    assert isinstance(seen.get("url"), str) and str(seen["url"]).endswith(":predict")
    assert isinstance(seen.get("json_body"), dict)
    assert seen["json_body"]["parameters"]["sampleCount"] == 1
    assert seen["json_body"]["parameters"]["aspectRatio"] == "16:9"
    assert seen["json_body"]["parameters"]["imageSize"] == "2K"
    payload = resp.json()
    assert payload["data"][0]["b64_json"] == "AAAD"
    assert payload["data"][0]["revised_prompt"] == "enhanced prompt"


def test_images_generations_url_format_returns_signed_media_url_when_oss_available(
    client, db_session, monkeypatch, api_key_auth_header
):
    _seed_provider_with_image_model(
        db_session,
        provider_id="google-like",
        model_id="gemini-2.5-flash-image",
        base_url="https://generativelanguage.googleapis.com",
    )

    async def _fake_call(**kwargs):
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": "AAAC",
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    async def _fake_store_image_b64(b64_data: str, *, content_type: str | None = None):
        class _Stored:
            object_key = "generated-images/2025/01/01/abc.png"
        return _Stored()

    def _fake_build_signed_url(object_key: str, *, base_url: str | None = None, ttl_seconds: int | None = None) -> str:
        return f"http://localhost:8000/media/images/{object_key}?expires=1700000001&sig=deadbeef"

    monkeypatch.setattr(
        "app.services.image_app_service.call_upstream_http_with_metrics", _fake_call
    )
    monkeypatch.setattr(
        "app.services.image_app_service.store_image_b64", _fake_store_image_b64
    )
    monkeypatch.setattr(
        "app.services.image_app_service.build_signed_image_url", _fake_build_signed_url
    )

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={"prompt": "a cat", "model": "gemini-2.5-flash-image", "n": 1, "response_format": "url"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data"][0]["url"].startswith("http://localhost:8000/media/images/")


def test_images_generations_url_format_falls_back_to_data_url_when_oss_not_configured(
    client, db_session, monkeypatch, api_key_auth_header
):
    _seed_provider_with_image_model(db_session, provider_id="openai-like", model_id="gpt-image-1")

    async def _fake_call(**kwargs):
        return httpx.Response(
            200,
            json={
                "created": 1700000000,
                "data": [{"b64_json": "iVBORw0KGgo=", "revised_prompt": "a cat"}],
            },
        )

    class _NotConfigured(Exception):
        pass

    async def _fake_store_image_b64(*args, **kwargs):
        raise _NotConfigured("not configured")

    monkeypatch.setattr(
        "app.services.image_app_service.call_upstream_http_with_metrics", _fake_call
    )
    monkeypatch.setattr(
        "app.services.image_app_service.ImageStorageNotConfigured", _NotConfigured
    )
    monkeypatch.setattr(
        "app.services.image_app_service.store_image_b64", _fake_store_image_b64
    )

    resp = client.post(
        "/v1/images/generations",
        headers=api_key_auth_header,
        json={"prompt": "a cat", "model": "gpt-image-1", "n": 1, "response_format": "url"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data"][0]["url"].startswith("data:image/")
