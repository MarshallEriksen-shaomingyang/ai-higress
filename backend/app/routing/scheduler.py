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
)


@dataclass
class CandidateScore:
    upstream: PhysicalModel
    score: float
    metrics: RoutingMetrics | None = None


def _normalise_latency(ms: float) -> float:
    """
    Normalise latency into [0, 1] range using a simple cap at 4000ms.
    """
    if ms <= 0:
        return 0.0
    cap = 4000.0
    return min(1.0, ms / cap)


def _status_penalty(metrics: RoutingMetrics | None, enable_check: bool = True) -> float:
    """
    计算基于 Provider 健康状态的惩罚分数。
    
    Args:
        metrics: Provider 的路由指标
        enable_check: 是否启用健康检查（由环境变量控制）
    
    Returns:
        惩罚分数：down=1.0, degraded=0.5, healthy=0.0
    """
    if not enable_check:
        return 0.0  # 健康检查关闭时不施加任何惩罚

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
    enable_health_check: bool = True,
) -> list[CandidateScore]:
    """
    Compute scores for upstream candidates.
    
    Args:
        logical_model: 逻辑模型
        upstreams: 物理模型候选列表
        metrics_by_provider: Provider 指标字典
        strategy: 调度策略
        dynamic_weights: 动态权重（可选）
        enable_health_check: 是否启用健康检查和最低分数过滤
    """
    from app.logging_config import logger

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
        quota_penalty = _status_penalty(metrics, enable_check=enable_health_check)

        score = (
            base
            - strategy.alpha * norm_lat
            - strategy.beta * err
            - strategy.gamma * cost_score
            - strategy.delta * quota_penalty
        )

        logger.info(
            f"🔍 Scoring upstream: provider={up.provider_id} model={up.model_id} "
            f"base={base:.2f} norm_lat={norm_lat:.2f} err={err:.2f} "
            f"quota_penalty={quota_penalty:.2f} score={score:.2f} min_score={strategy.min_score:.2f} "
            f"health_check={'enabled' if enable_health_check else 'disabled'}"
        )

        # 根据配置决定是否应用 min_score 过滤
        if enable_health_check and score < strategy.min_score:
            logger.warning(
                f"❌ Filtered out {up.provider_id}/{up.model_id}: "
                f"score {score:.2f} < min_score {strategy.min_score:.2f}"
            )
            continue

        results.append(CandidateScore(upstream=up, metrics=metrics, score=score))

    # Highest score first.
    results.sort(key=lambda c: c.score, reverse=True)
    logger.info(f"✅ Total scored candidates: {len(results)}")
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
    dynamic_weights: dict[str, float] | None = None,
    enable_health_check: bool = True,
) -> tuple[CandidateScore, list[CandidateScore]]:
    """
    Choose a single upstream using scoring.
    Returns (selected, all_scored_candidates).
    
    Args:
        logical_model: 逻辑模型
        upstreams: 物理模型候选列表
        metrics_by_provider: Provider 指标字典
        strategy: 调度策略
        dynamic_weights: 动态权重（可选）
        enable_health_check: 是否启用健康检查和最低分数过滤
    """
    scored = score_upstreams(
        logical_model, upstreams, metrics_by_provider, strategy, dynamic_weights, enable_health_check
    )
    if not scored:
        raise RuntimeError("No eligible upstream candidates")

    # No sticky session match; fall back to weighted random choice based
    # on scores so that traffic can be balanced across healthy upstreams.
    selected = _weighted_choice(scored)
    return selected, scored


__all__ = ["CandidateScore", "choose_upstream", "score_upstreams"]
