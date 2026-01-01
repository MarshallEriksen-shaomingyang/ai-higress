from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.audio import SpeechRequest
from app.services.tts_app_service import _build_gemini_tts_payload, _build_openai_compatible_tts_payload


@pytest.mark.parametrize("case", json.loads(Path(__file__).with_name("fixtures").joinpath("tts_golden_payloads.json").read_text(encoding="utf-8")))
def test_tts_golden_payloads(case: dict) -> None:
    kind = case.get("kind")
    request = SpeechRequest(**(case.get("request") or {}))
    processed_text = str(case.get("processed_text") or "")
    expected = case.get("expected")

    if kind == "openai":
        allow_extensions = bool(case.get("allow_extensions", False))
        payload = _build_openai_compatible_tts_payload(
            provider_model_id=str(case.get("provider_model_id") or ""),
            processed_text=processed_text,
            request=request,
            allow_extensions=allow_extensions,
        )
        assert payload == expected
        return

    if kind == "gemini":
        payload = _build_gemini_tts_payload(request=request, processed_text=processed_text)
        assert payload == expected
        return

    raise AssertionError(f"unknown golden payload kind: {kind!r} (case={case.get('name')})")
