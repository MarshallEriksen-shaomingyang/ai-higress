from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.routing_state import RoutingStateService
from app.provider.health import HealthStatus
from app.schemas import LogicalModel, PhysicalModel, ProviderStatus


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
    routing_state.get_failure_cooldown_status = AsyncMock(
        return_value=MagicMock(should_skip=False)
    )
    # Mock load_disabled_pairs default to empty set
    provider_selector = ProviderSelector(
        client=mock_client, redis=mock_redis, db=mock_db, routing_state=routing_state
    )
    provider_selector._load_disabled_pairs = MagicMock(return_value=set())
    return provider_selector

@pytest.fixture
def sample_logical_model():
    from datetime import datetime
    now = datetime.now().timestamp()
    return LogicalModel(
        logical_id="model-a",
        display_name="Model A",
        description="A model",
        capabilities=["chat"],
        upstreams=[
            PhysicalModel(
                provider_id="prov-1",
                model_id="model-a-1",
                endpoint="http://p1",
                base_weight=1.0,
                updated_at=now,
                api_style="openai"
            ),
            PhysicalModel(
                provider_id="prov-2",
                model_id="model-a-2",
                endpoint="http://p2",
                base_weight=1.0,
                updated_at=now,
                api_style="openai"
            ),
        ],
        strategy={"name": "balanced"},
        updated_at=now,
        enabled=True
    )

@pytest.mark.asyncio
async def test_check_candidate_availability(provider_selector, sample_logical_model):
    # Setup
    with patch.object(provider_selector, "_resolve_logical_model") as mock_resolve, \
         patch("app.api.v1.chat.provider_selector.select_candidate_upstreams") as mock_select_upstreams, \
         patch("app.api.v1.chat.provider_selector.settings") as mock_settings:

        mock_settings.enable_provider_health_check = True
        mock_settings.candidate_availability_cache_ttl_seconds = 0
        mock_resolve.return_value = sample_logical_model
        mock_select_upstreams.return_value = list(sample_logical_model.upstreams)

        # Test 1: All available
        provider_selector.routing_state.get_cached_health_status.return_value = None

        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"}
        )
        assert available == ["model-a"]

        # Test 2: One provider restricted (but model still available via another)
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1"}
        )
        assert available == ["model-a"]

        # Test 3: All providers restricted
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-3"}
        )
        assert available == []

        # Test 4: One provider down (but model still available via another)
        # Note: side_effect overrides return_value
        def health_side_effect(pid):
             if pid == "prov-1":
                 return HealthStatus(provider_id="prov-1", status=ProviderStatus.DOWN, timestamp=0, error_message=None)
             return None

        provider_selector.routing_state.get_cached_health_status.side_effect = health_side_effect

        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"}
        )
        assert available == ["model-a"]
        provider_selector.routing_state.get_cached_health_status.side_effect = None

        # Test 5: All providers down
        provider_selector.routing_state.get_cached_health_status.return_value = HealthStatus(provider_id="dummy", status=ProviderStatus.DOWN, timestamp=0, error_message=None)

        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"}
        )
        assert available == []
        provider_selector.routing_state.get_cached_health_status.return_value = None

        # Test 6: Disabled pair
        provider_selector._load_disabled_pairs.return_value = {("prov-1", "model-a-1")}

        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1"} # Only prov-1 allowed, but disabled
        )
        assert available == []

        # Test 7: Disabled pair (but other provider available)
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"}
        )
        assert available == ["model-a"]

        # Test 8: All providers degraded => model not feasible
        provider_selector._load_disabled_pairs.return_value = set()
        provider_selector.routing_state.get_cached_health_status.return_value = HealthStatus(
            provider_id="dummy",
            status=ProviderStatus.DEGRADED,
            timestamp=0,
            error_message=None,
        )
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"},
        )
        assert available == []
        provider_selector.routing_state.get_cached_health_status.return_value = None

        # Test 9: Failure cooldown skips one provider (still feasible via another)
        def cooldown_side_effect(pid):
            return MagicMock(should_skip=pid == "prov-1")

        provider_selector.routing_state.get_failure_cooldown_status.side_effect = cooldown_side_effect
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"},
        )
        assert available == ["model-a"]

        # Test 10: Failure cooldown skips all providers
        def cooldown_all(_pid):
            return MagicMock(should_skip=True)

        provider_selector.routing_state.get_failure_cooldown_status.side_effect = cooldown_all
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"},
        )
        assert available == []
        provider_selector.routing_state.get_failure_cooldown_status.side_effect = None

        # Test 11: Capability constraints inferred from request_payload.tools
        available = await provider_selector.check_candidate_availability(
            candidate_logical_models=["model-a"],
            effective_provider_ids={"prov-1", "prov-2"},
            request_payload={"tools": [{"type": "function", "function": {"name": "x"}}]},
        )
        assert available == []

        # Test 12: Budget feasibility (filter by estimated credits)
        with patch(
            "app.api.v1.chat.provider_selector.estimate_request_cost_credits"
        ) as mock_estimate:
            mock_estimate.side_effect = lambda _db, **kw: 10 if kw.get("provider_id") == "prov-1" else 3
            available = await provider_selector.check_candidate_availability(
                candidate_logical_models=["model-a"],
                effective_provider_ids={"prov-1", "prov-2"},
                request_payload={"max_tokens": 1000},
                budget_credits=5,
            )
            assert available == ["model-a"]

            mock_estimate.side_effect = None
            mock_estimate.return_value = 999
            available = await provider_selector.check_candidate_availability(
                candidate_logical_models=["model-a"],
                effective_provider_ids={"prov-1", "prov-2"},
                request_payload={"max_tokens": 1000},
                budget_credits=5,
            )
            assert available == []
