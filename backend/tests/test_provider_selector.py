"""
测试 ProviderSelector（v2）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.routing.scheduler import CandidateScore
from app.schemas import LogicalModel, PhysicalModel, RoutingMetrics


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def provider_selector(mock_client, mock_redis, mock_db):
    routing_state = MagicMock(spec=RoutingStateService)
    routing_state.get_cached_health_status = AsyncMock(return_value=None)
    routing_state.load_metrics_for_candidates = AsyncMock(return_value={})
    routing_state.load_dynamic_weights = AsyncMock(return_value={})
    provider_selector = ProviderSelector(
        client=mock_client, redis=mock_redis, db=mock_db, routing_state=routing_state
    )
    # Avoid hitting mocked DB internals in unit tests.
    provider_selector._load_disabled_pairs = MagicMock(return_value=set())
    return provider_selector


@pytest.fixture
def sample_logical_model():
    from datetime import datetime

    now = datetime.now().timestamp()
    return LogicalModel(
        logical_id="gpt-4",
        display_name="GPT-4",
        description="GPT-4 model",
        capabilities=["chat"],
        upstreams=[
            PhysicalModel(
                provider_id="openai",
                model_id="gpt-4-turbo",
                endpoint="https://api.openai.com/v1/chat/completions",
                base_weight=1.0,
                updated_at=now,
            ),
            PhysicalModel(
                provider_id="azure",
                model_id="gpt-4",
                endpoint="https://azure.openai.com/v1/chat/completions",
                base_weight=0.8,
                updated_at=now,
            ),
        ],
        strategy={"name": "balanced"},
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_select_orders_candidates_selected_first(provider_selector, sample_logical_model):
    with patch.object(provider_selector, "_resolve_logical_model") as mock_resolve, patch(
        "app.api.v1.chat.provider_selector.select_candidate_upstreams"
    ) as mock_select_upstreams, patch(
        "app.api.v1.chat.provider_selector.choose_upstream"
    ) as mock_choose, patch(
        "app.api.v1.chat.provider_selector.settings"
    ) as mock_settings:
        mock_settings.enable_provider_health_check = False
        mock_resolve.return_value = sample_logical_model
        mock_select_upstreams.return_value = list(sample_logical_model.upstreams)

        selected = CandidateScore(upstream=sample_logical_model.upstreams[1], score=0.9, metrics=None)
        scored = [
            selected,
            CandidateScore(upstream=sample_logical_model.upstreams[0], score=0.8, metrics=None),
        ]
        mock_choose.return_value = (selected, scored)

        result = await provider_selector.select(
            requested_model="gpt-4",
            lookup_model_id="gpt-4",
            api_style="openai",
            effective_provider_ids={"openai", "azure"},
            user_id=None,
            is_superuser=False,
        )

        assert result.logical_model.logical_id == "gpt-4"
        assert result.ordered_candidates[0].upstream.provider_id == "azure"


@pytest.mark.asyncio
async def test_select_filters_by_effective_provider_ids(provider_selector, sample_logical_model):
    with patch.object(provider_selector, "_resolve_logical_model") as mock_resolve, patch(
        "app.api.v1.chat.provider_selector.select_candidate_upstreams"
    ) as mock_select_upstreams, patch(
        "app.api.v1.chat.provider_selector.choose_upstream"
    ) as mock_choose, patch(
        "app.api.v1.chat.provider_selector.settings"
    ) as mock_settings:
        mock_settings.enable_provider_health_check = False
        mock_resolve.return_value = sample_logical_model
        mock_select_upstreams.return_value = list(sample_logical_model.upstreams)

        def _choose_side_effect(logical_model, upstreams, *_args, **_kwargs):
            assert [u.provider_id for u in upstreams] == ["openai"]
            selected = CandidateScore(upstream=upstreams[0], score=1.0, metrics=None)
            return selected, [selected]

        mock_choose.side_effect = _choose_side_effect

        result = await provider_selector.select(
            requested_model="gpt-4",
            lookup_model_id="gpt-4",
            api_style="openai",
            effective_provider_ids={"openai"},
            user_id=None,
            is_superuser=False,
        )

        assert len(result.ordered_candidates) == 1
        assert result.ordered_candidates[0].upstream.provider_id == "openai"


@pytest.mark.asyncio
async def test_select_uses_state_metrics_and_weights(provider_selector, sample_logical_model):
    state_metrics = {
        "openai": RoutingMetrics(
            logical_model="gpt-4",
            provider_id="openai",
            latency_p95_ms=100.0,
            latency_p99_ms=150.0,
            error_rate=0.01,
            success_qps_1m=10.0,
            total_requests_1m=100,
            last_updated=123.0,
            status="healthy",
        )
    }
    provider_selector.routing_state.load_metrics_for_candidates = AsyncMock(return_value=state_metrics)
    provider_selector.routing_state.load_dynamic_weights = AsyncMock(return_value={"openai": 1.2})

    with patch.object(provider_selector, "_resolve_logical_model") as mock_resolve, patch(
        "app.api.v1.chat.provider_selector.select_candidate_upstreams"
    ) as mock_select_upstreams, patch(
        "app.api.v1.chat.provider_selector.choose_upstream"
    ) as mock_choose, patch(
        "app.api.v1.chat.provider_selector.settings"
    ) as mock_settings:
        mock_settings.enable_provider_health_check = False
        mock_resolve.return_value = sample_logical_model
        mock_select_upstreams.return_value = list(sample_logical_model.upstreams)

        def _choose_side_effect(_lm, _upstreams, metrics_by_provider, *_args, **kwargs):
            assert metrics_by_provider == state_metrics
            assert kwargs.get("dynamic_weights") == {"openai": 1.2}
            selected = CandidateScore(upstream=sample_logical_model.upstreams[0], score=1.0, metrics=None)
            return selected, [selected]

        mock_choose.side_effect = _choose_side_effect

        await provider_selector.select(
            requested_model="gpt-4",
            lookup_model_id="gpt-4",
            api_style="openai",
            effective_provider_ids={"openai", "azure"},
            user_id=None,
            is_superuser=False,
        )

        provider_selector.routing_state.load_metrics_for_candidates.assert_awaited()
        provider_selector.routing_state.load_dynamic_weights.assert_awaited()


@pytest.mark.asyncio
async def test_resolve_logical_model_passes_allowed_provider_ids(provider_selector, sample_logical_model):
    with patch("app.api.v1.chat.provider_selector.get_logical_model", new=AsyncMock(return_value=None)), patch(
        "app.api.v1.chat.provider_selector._build_dynamic_logical_model_for_group", new=AsyncMock(return_value=sample_logical_model)
    ) as mock_build:
        lm = await provider_selector._resolve_logical_model(
            requested_model="gpt-4",
            lookup_model_id="gpt-4",
            api_style="openai",
            allowed_provider_ids={"a4f", "runanytime"},
            user_id=None,
            is_superuser=False,
        )
        assert lm.logical_id == "gpt-4"
        assert mock_build.call_args.kwargs["allowed_provider_ids"] == {"a4f", "runanytime"}
