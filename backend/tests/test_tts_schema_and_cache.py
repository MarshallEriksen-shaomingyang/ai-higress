from __future__ import annotations

import pytest

from app.schemas.audio import SpeechRequest
from tests.utils import InMemoryRedis


@pytest.mark.parametrize("fmt", ["ogg", "flac", "aiff"])
def test_speech_request_accepts_extended_response_formats(fmt: str) -> None:
    req = SpeechRequest(
        model="auto",
        input="hello",
        voice="alloy",
        response_format=fmt,
        speed=1.0,
    )
    assert req.response_format == fmt


def test_speech_request_accepts_optional_standard_and_advanced_fields() -> None:
    req = SpeechRequest(
        model="auto",
        input="hello",
        voice="alloy",
        response_format="mp3",
        speed=1.0,
        input_type="text",
        locale="zh-CN",
        pitch=0.2,
        volume=0.8,
        reference_audio_url="https://example.com/ref.wav",
    )
    assert req.input_type == "text"
    assert req.locale == "zh-CN"
    assert req.pitch == 0.2
    assert req.volume == 0.8
    assert str(req.reference_audio_url) == "https://example.com/ref.wav"


def test_speech_request_defaults_input_type_to_text() -> None:
    req = SpeechRequest(
        model="auto",
        input="hello",
        voice="alloy",
        response_format="mp3",
        speed=1.0,
    )
    assert req.input_type == "text"


@pytest.mark.asyncio
async def test_inmemory_redis_bytes_roundtrip() -> None:
    redis = InMemoryRedis()
    payload = b"\x00\x01hello\xff"
    await redis.set("k", payload, ex=10)
    got = await redis.get("k")
    assert got == payload
