from __future__ import annotations

from sqlalchemy import select

from app.api.v1.chat.provider_selector import ProviderSelectionResult, ProviderSelector
from app.models import Provider, ProviderModel
from app.routing.scheduler import CandidateScore
from app.schemas import LogicalModel, ModelCapability, PhysicalModel


def test_tts_missing_reference_audio_url_filters_out_required_upstreams(client, db_session, api_key_auth_header, monkeypatch):
    provider = (
        db_session.execute(select(Provider).where(Provider.provider_id == "mock"))
        .scalars()
        .first()
    )
    assert provider is not None

    model_id = "tts-clone-1"
    db_session.add(
        ProviderModel(
            provider_id=provider.id,
            model_id=model_id,
            alias=None,
            family="tts",
            display_name="tts-clone-1",
            context_length=8192,
            capabilities=["audio"],
            pricing=None,
            metadata_json={"_gateway": {"tts": {"requires_reference_audio": True}}},
            meta_hash=None,
        )
    )
    db_session.commit()

    physical = PhysicalModel(
        provider_id=provider.provider_id,
        model_id=model_id,
        endpoint="/v1/audio/speech",
        base_weight=1.0,
        region=None,
        max_qps=None,
        meta_hash=None,
        updated_at=0.0,
        api_style="openai",
    )
    logical = LogicalModel(
        logical_id="tts-test",
        display_name="tts-test",
        description="tts-test",
        capabilities=[ModelCapability.AUDIO],
        upstreams=[physical],
        enabled=True,
        updated_at=0.0,
    )
    scored = CandidateScore(upstream=physical, score=1.0, metrics=None)

    async def _fake_select(self, **kwargs):  # type: ignore[no-untyped-def]
        return ProviderSelectionResult(
            logical_model=logical,
            ordered_candidates=[scored],
            scored_candidates=[scored],
            base_weights={provider.provider_id: 1.0},
        )

    monkeypatch.setattr(ProviderSelector, "select", _fake_select, raising=True)

    resp = client.post(
        "/v1/audio/speech",
        headers=api_key_auth_header,
        json={
            "model": "auto",
            "input": "hello",
            "voice": "alloy",
            "response_format": "mp3",
            "speed": 1.0,
        },
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail") or {}
    assert detail.get("missing_field") == "reference_audio_url"
