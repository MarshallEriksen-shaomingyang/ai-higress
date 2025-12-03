"""
Routing scheduler for selecting the best upstream model.

Implements a simple scoring algorithm based on the research in
specs/001-model-routing/research.md. This module is pure and does not
talk to Redis directly.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas import (
    LogicalModel,
    PhysicalModel,
    RoutingMetrics,
    SchedulingStrategy,
    Session,
)


@dataclass
class CandidateScore:
    upstream: PhysicalModel
    metrics: RoutingMetrics | None
    score: float


def _normalise_latency(ms: float) -> float:
    """
    Normalise latency into [0, 1] range using a simple cap at 4000ms.
    """
    if ms <= 0:
        return 0.0
    cap = 4000.0
    return min(1.0, ms / cap)


def _status_penalty(metrics: RoutingMetrics | None) -> float:
    if metrics is None:
        return 0.0
    if metrics.status.value == "down":
        return 1.0
    if metrics.status.value == "degraded":
        return 0.5
    return 0.0


def score_upstreams(
    logical_model: LogicalModel,
    upstreams: Sequence[PhysicalModel],
    metrics_by_provider: dict[str, RoutingMetrics],
    strategy: SchedulingStrategy,
    dynamic_weights: dict[str, float] | None = None,
) -> list[CandidateScore]:
    """
    Compute scores for upstream candidates.
    """
    results: list[CandidateScore] = []
    for up in upstreams:
        metrics = metrics_by_provider.get(up.provider_id)

        # Base weight from mapping.
        if dynamic_weights:
            base = dynamic_weights.get(up.provider_id, up.base_weight)
        else:
            base = up.base_weight

        # Latency / error contributions.
        if metrics is not None:
            norm_lat = _normalise_latency(metrics.latency_p95_ms)
            err = metrics.error_rate
        else:
            norm_lat = 0.5
            err = 0.0

        # Cost and quota components are left as zero for now; they can be
        # plugged in later when we track them explicitly.
        cost_score = 0.0
        quota_penalty = _status_penalty(metrics)

        score = (
            base
            - strategy.alpha * norm_lat
            - strategy.beta * err
            - strategy.gamma * cost_score
            - strategy.delta * quota_penalty
        )

        if score < strategy.min_score:
            continue

        results.append(CandidateScore(upstream=up, metrics=metrics, score=score))

    # Highest score first.
    results.sort(key=lambda c: c.score, reverse=True)
    return results


def _weighted_choice(candidates: Sequence[CandidateScore]) -> CandidateScore:
    """
    Pick one candidate using its score as weight.

    When all scores are non-positive (should not normally happen because
    of min_score), we fall back to uniform random choice.
    """
    if not candidates:
        raise RuntimeError("Cannot choose from empty candidates")

    # Use max(score, 0.0) so that very low scores do not invert weights.
    weights: list[float] = [max(c.score, 0.0) for c in candidates]
    total = sum(weights)

    if total <= 0.0:
        # Fallback: all weights are zero or negative, choose uniformly.
        return random.choice(list(candidates))

    r = random.random() * total
    acc = 0.0
    for cand, w in zip(candidates, weights):
        acc += w
        if r <= acc:
            return cand

    # Numerical safety net.
    return candidates[-1]


def choose_upstream(
    logical_model: LogicalModel,
    upstreams: Sequence[PhysicalModel],
    metrics_by_provider: dict[str, RoutingMetrics],
    strategy: SchedulingStrategy,
    session: Session | None = None,
    dynamic_weights: dict[str, float] | None = None,
) -> tuple[CandidateScore, list[CandidateScore]]:
    """
    Choose a single upstream using scoring and optional session stickiness.
    Returns (selected, all_scored_candidates).
    """
    scored = score_upstreams(
        logical_model, upstreams, metrics_by_provider, strategy, dynamic_weights
    )
    if not scored:
        raise RuntimeError("No eligible upstream candidates")

    # Stickiness: if there is an existing session and its provider+model
    # is still in the candidate list, prefer it regardless of raw score.
    if strategy.enable_stickiness and session is not None:
        for cand in scored:
            if (
                cand.upstream.provider_id == session.provider_id
                and cand.upstream.model_id == session.model_id
            ):
                return cand, scored

    # No sticky session match; fall back to weighted random choice based
    # on scores so that traffic can be balanced across healthy upstreams.
    selected = _weighted_choice(scored)
    return selected, scored


__all__ = ["CandidateScore", "choose_upstream", "score_upstreams"]
