
from app.routing.metrics import aggregate_metrics
from app.schemas import MetricsHistory, ProviderStatus


def test_aggregate_metrics_basic():
    samples: list[MetricsHistory] = [
        MetricsHistory(
            provider_id="openai",
            logical_model="gpt-4",
            timestamp=1.0,
            latency_ms=100.0,
            success=True,
        ),
        MetricsHistory(
            provider_id="openai",
            logical_model="gpt-4",
            timestamp=2.0,
            latency_ms=200.0,
            success=True,
        ),
        MetricsHistory(
            provider_id="openai",
            logical_model="gpt-4",
            timestamp=3.0,
            latency_ms=300.0,
            success=False,
        ),
    ]

    metrics = aggregate_metrics("gpt-4", "openai", samples)

    assert metrics.logical_model == "gpt-4"
    assert metrics.provider_id == "openai"
    assert metrics.total_requests_1m == 3
    assert metrics.error_rate == 1 / 3
    assert metrics.status in {ProviderStatus.HEALTHY, ProviderStatus.DEGRADED, ProviderStatus.DOWN}

