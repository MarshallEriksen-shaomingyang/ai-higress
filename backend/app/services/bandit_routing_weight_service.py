from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.routing.provider_weight import clamp_provider_weight
from app.schemas import PhysicalModel
from app.services.bandit_policy_service import BanditRecommendation, recommend_challengers
from app.services.context_features_service import build_rule_context_features

_ARM_PREFIX_LOGICAL_MODEL = "lm:"
_ARM_PREFIX_PROVIDER = "provider:"


def build_provider_arm_key(*, logical_model_id: str, provider_id: str) -> str:
    logical = (logical_model_id or "").strip()
    provider = (provider_id or "").strip()
    return f"{_ARM_PREFIX_LOGICAL_MODEL}{logical}|{_ARM_PREFIX_PROVIDER}{provider}"


def parse_provider_arm_key(arm_key: str) -> tuple[str, str] | None:
    if not isinstance(arm_key, str):
        return None
    raw = arm_key.strip()
    if not raw:
        return None
    if "|" not in raw:
        return None
    left, right = raw.split("|", 1)
    if not left.startswith(_ARM_PREFIX_LOGICAL_MODEL):
        return None
    if not right.startswith(_ARM_PREFIX_PROVIDER):
        return None
    logical_model_id = left[len(_ARM_PREFIX_LOGICAL_MODEL) :].strip()
    provider_id = right[len(_ARM_PREFIX_PROVIDER) :].strip()
    if not logical_model_id or not provider_id:
        return None
    return logical_model_id, provider_id


def compute_rank_boost_factors(
    recommendation: BanditRecommendation,
    *,
    logical_model_id: str,
    top_n: int,
    max_boost: float,
    decay: float,
) -> dict[str, float]:
    if top_n <= 0 or max_boost <= 0:
        return {}
    safe_decay = float(decay)
    if safe_decay <= 0:
        safe_decay = 0.0
    if safe_decay > 1.0:
        safe_decay = 1.0

    factors: dict[str, float] = {}
    ranked = recommendation.candidates or []
    for rank, item in enumerate(ranked[:top_n]):
        parsed = parse_provider_arm_key(item.logical_model)
        if parsed is None:
            continue
        arm_logical_model, provider_id = parsed
        if arm_logical_model != logical_model_id:
            continue
        boost = float(max_boost) * (safe_decay**rank)
        factor = 1.0 + boost
        if factor <= 0:
            continue
        factors[provider_id] = factor
    return factors


def apply_boost_factors_to_weights(
    *,
    base_weights: dict[str, float],
    current_weights: dict[str, float] | None,
    boost_factors: dict[str, float],
) -> dict[str, float]:
    effective: dict[str, float] = {}
    for provider_id, base_weight in (base_weights or {}).items():
        base = float(base_weight or 1.0)
        current = float((current_weights or {}).get(provider_id, base))
        factor = float(boost_factors.get(provider_id, 1.0))
        weighted = current * factor
        effective[provider_id] = clamp_provider_weight(weighted, base)
    return effective


@dataclass(frozen=True)
class BanditRoutingWeightsResult:
    recommendation: BanditRecommendation
    boost_factors: dict[str, float]
    dynamic_weights: dict[str, float]


def build_bandit_routing_weights(
    db: Session,
    *,
    project_id: UUID,
    assistant_id: UUID,
    logical_model_id: str,
    upstreams: list[PhysicalModel],
    user_text: str,
    request_payload: dict[str, Any] | None,
    base_weights: dict[str, float],
    current_weights: dict[str, float] | None,
    top_n: int,
    max_boost: float,
    decay: float,
    min_samples_per_arm: int,
    apply_during_exploration: bool,
    policy_version: str = "ts-routing-v1",
    context_features: dict[str, str] | None = None,
) -> BanditRoutingWeightsResult | None:
    provider_ids = [u.provider_id for u in (upstreams or []) if getattr(u, "provider_id", None)]
    provider_ids = list(dict.fromkeys(provider_ids))
    if len(provider_ids) <= 1:
        return None
    if not isinstance(user_text, str) or not user_text.strip():
        return None

    features = dict(context_features) if context_features else build_rule_context_features(
        user_text=user_text,
        request_payload=request_payload if isinstance(request_payload, dict) else None,
    )

    candidate_arms = [
        build_provider_arm_key(logical_model_id=logical_model_id, provider_id=pid)
        for pid in provider_ids
    ]

    rec = recommend_challengers(
        db,
        project_id=project_id,
        assistant_id=assistant_id,
        baseline_logical_model="",
        user_text=user_text,
        context_features=features,
        candidate_logical_models=candidate_arms,
        k=len(candidate_arms),
        policy_version=policy_version,
    )
    if not rec.candidates:
        return None

    if rec.exploration and not apply_during_exploration:
        max_samples = max((c.samples for c in rec.candidates), default=0)
        if max_samples < int(min_samples_per_arm or 0):
            return None

    boost_factors = compute_rank_boost_factors(
        rec,
        logical_model_id=logical_model_id,
        top_n=top_n,
        max_boost=max_boost,
        decay=decay,
    )
    if not boost_factors:
        return None

    dynamic_weights = apply_boost_factors_to_weights(
        base_weights=base_weights,
        current_weights=current_weights,
        boost_factors=boost_factors,
    )
    if not dynamic_weights:
        return None

    return BanditRoutingWeightsResult(
        recommendation=rec,
        boost_factors=boost_factors,
        dynamic_weights=dynamic_weights,
    )


__all__ = [
    "BanditRoutingWeightsResult",
    "apply_boost_factors_to_weights",
    "build_bandit_routing_weights",
    "build_provider_arm_key",
    "compute_rank_boost_factors",
    "parse_provider_arm_key",
]

