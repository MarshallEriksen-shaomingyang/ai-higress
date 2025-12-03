"""
Runtime metrics collection and aggregation helpers.

This module provides pure functions to aggregate MetricsHistory samples
into a RoutingMetrics snapshot, plus small helpers that can be wired to
Redis storage. It is intentionally simple and focuses on the behaviour
needed by the scheduler and tests.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.schemas import MetricsHistory, ProviderStatus, RoutingMetrics


def aggregate_metrics(
    logical_model: str, provider_id: str, samples: Iterable[MetricsHistory]
) -> RoutingMetrics:
    """
    Aggregate a collection of MetricsHistory samples into a RoutingMetrics.

    Assumptions for now:
    - `samples` already represent roughly a 1-minute window.
    - success_qps_1m is approximated as success_count / 60.0.
    """
    samples_list: list[MetricsHistory] = list(samples)
    if not samples_list:
        raise ValueError("Cannot aggregate empty metrics history")

    total = len(samples_list)
    latencies = sorted(s.latency_ms for s in samples_list)
    failures = sum(1 for s in samples_list if not s.success)
    success_count = total - failures

    def _percentile(p: float) -> float:
        idx = max(0, min(total - 1, int(round(p * (total - 1)))))
        return float(latencies[idx])

    latency_p95 = _percentile(0.95)
    latency_p99 = _percentile(0.99)
    error_rate = failures / total if total else 0.0
    success_qps_1m = success_count / 60.0
    last_updated = max(s.timestamp for s in samples_list)

    # Derive a coarse status value based on latency and error rate.
    if error_rate > 0.5:
        status = ProviderStatus.DOWN
    elif error_rate > 0.1 or latency_p95 > 2000:
        status = ProviderStatus.DEGRADED
    else:
        status = ProviderStatus.HEALTHY

    return RoutingMetrics(
        logical_model=logical_model,
        provider_id=provider_id,
        latency_p95_ms=latency_p95,
        latency_p99_ms=latency_p99,
        error_rate=error_rate,
        success_qps_1m=success_qps_1m,
        total_requests_1m=total,
        last_updated=last_updated,
        status=status,
    )


__all__ = ["aggregate_metrics"]

