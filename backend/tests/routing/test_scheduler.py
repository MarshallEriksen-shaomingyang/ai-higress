
from app.routing.scheduler import CandidateScore, choose_upstream, score_upstreams
from app.schemas import LogicalModel, ModelCapability, PhysicalModel, RoutingMetrics, SchedulingStrategy


def _logical_and_upstreams():
    logical = LogicalModel(
        logical_id="gpt-4",
        display_name="GPT-4",
        description="Test logical model",
        capabilities=[ModelCapability.CHAT],
        upstreams=[],
        enabled=True,
        updated_at=1704067200.0,
    )
    upstreams = [
        PhysicalModel(
            provider_id="fast",
            model_id="gpt-4",
            endpoint="https://fast.example.com/v1/chat/completions",
            base_weight=1.0,
            region="global",
            max_qps=50,
            meta_hash=None,
            updated_at=1704067200.0,
        ),
        PhysicalModel(
            provider_id="slow",
            model_id="gpt-4",
            endpoint="https://slow.example.com/v1/chat/completions",
            base_weight=1.0,
            region="global",
            max_qps=50,
            meta_hash=None,
            updated_at=1704067200.0,
        ),
    ]
    logical.upstreams = upstreams
    return logical, upstreams


def test_score_upstreams_prefers_lower_latency():
    logical, upstreams = _logical_and_upstreams()
    strategy = SchedulingStrategy(name="balanced", description="test")
    metrics_by_provider: dict[str, RoutingMetrics] = {
        "fast": RoutingMetrics(
            logical_model="gpt-4",
            provider_id="fast",
            latency_p95_ms=100.0,
            latency_p99_ms=150.0,
            error_rate=0.01,
            success_qps_1m=10.0,
            total_requests_1m=10,
            last_updated=1.0,
            status="healthy",
        ),
        "slow": RoutingMetrics(
            logical_model="gpt-4",
            provider_id="slow",
            latency_p95_ms=2000.0,
            latency_p99_ms=2500.0,
            error_rate=0.01,
            success_qps_1m=10.0,
            total_requests_1m=10,
            last_updated=1.0,
            status="healthy",
        ),
    }

    scored: list[CandidateScore] = score_upstreams(
        logical, upstreams, metrics_by_provider, strategy
    )
    assert scored
    assert scored[0].upstream.provider_id == "fast"

def test_score_upstreams_respects_dynamic_weights():
    logical, upstreams = _logical_and_upstreams()
    strategy = SchedulingStrategy(name="balanced", description="test")
    dynamic_weights = {"fast": 0.5, "slow": 3.0}

    scored = score_upstreams(
        logical,
        upstreams,
        metrics_by_provider={},
        strategy=strategy,
        dynamic_weights=dynamic_weights,
    )

    assert scored
    assert scored[0].upstream.provider_id == "slow"
    assert scored[0].score > scored[-1].score
