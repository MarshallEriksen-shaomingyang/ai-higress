from __future__ import annotations

import hmac
import json
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BanditArmStats
from app.settings import settings

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def infer_language(text: str) -> str:
    if _CJK_RE.search(text or ""):
        return "zh"
    return "en"


def length_bucket(text: str) -> str:
    size = len(text or "")
    if size <= 200:
        return "short"
    if size <= 800:
        return "medium"
    return "long"


def build_context_features(
    *,
    user_text: str,
    tool_mode: str = "none",
    task_type: str = "unknown",
    risk_tier: str = "low",
) -> dict:
    return {
        "language": infer_language(user_text),
        "length_bucket": length_bucket(user_text),
        "tool_mode": tool_mode,
        "task_type": task_type,
        "risk_tier": risk_tier,
    }


def build_context_key(
    *,
    project_id: UUID,
    assistant_id: UUID,
    features: dict,
) -> str:
    secret = settings.secret_key.encode("utf-8")
    payload = json.dumps(
        {"project_id": str(project_id), "assistant_id": str(assistant_id), "features": features},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(secret, payload, sha256).hexdigest()[:64]


@dataclass(frozen=True)
class CandidateScore:
    logical_model: str
    sampled_score: float
    samples: int


@dataclass(frozen=True)
class BanditRecommendation:
    policy_version: str
    context_key: str
    features: dict
    candidates: list[CandidateScore]
    exploration: bool


def recommend_challengers(
    db: Session,
    *,
    project_id: UUID,
    assistant_id: UUID,
    baseline_logical_model: str,
    user_text: str,
    context_features: dict | None = None,
    candidate_logical_models: list[str],
    k: int,
    policy_version: str = "ts-v1",
) -> BanditRecommendation:
    if isinstance(context_features, dict) and context_features:
        features = dict(context_features)
    else:
        features = build_context_features(user_text=user_text)
    context_key = build_context_key(project_id=project_id, assistant_id=assistant_id, features=features)

    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for raw in candidate_logical_models or []:
        val = str(raw).strip()
        if not val or val == baseline_logical_model:
            continue
        if val in seen:
            continue
        normalized_candidates.append(val)
        seen.add(val)

    if not normalized_candidates:
        return BanditRecommendation(
            policy_version=policy_version,
            context_key=context_key,
            features=features,
            candidates=[],
            exploration=True,
        )

    rows = db.execute(
        select(BanditArmStats).where(
            BanditArmStats.api_key_id == project_id,
            BanditArmStats.assistant_id == assistant_id,
            BanditArmStats.context_key == context_key,
            BanditArmStats.arm_logical_model.in_(normalized_candidates),
        )
    ).scalars().all()
    stats_by_arm = {row.arm_logical_model: row for row in rows}

    scored: list[CandidateScore] = []
    exploration = False
    for arm in normalized_candidates:
        stat = stats_by_arm.get(arm)
        if stat is None:
            exploration = True
            alpha = 1.0
            beta = 1.0
            samples = 0
        else:
            alpha = float(stat.alpha or 1.0)
            beta = float(stat.beta or 1.0)
            samples = int(stat.samples or 0)
            if samples < 10:
                exploration = True
        sampled = random.betavariate(alpha, beta)
        scored.append(CandidateScore(logical_model=arm, sampled_score=float(sampled), samples=samples))

    scored.sort(key=lambda item: item.sampled_score, reverse=True)
    if k <= 0:
        topk = []
    else:
        topk = scored[:k]

    return BanditRecommendation(
        policy_version=policy_version,
        context_key=context_key,
        features=features,
        candidates=topk,
        exploration=exploration,
    )


def apply_winner_update(
    db: Session,
    *,
    project_id: UUID,
    assistant_id: UUID,
    context_key: str,
    candidate_models: list[str],
    winner_model: str,
) -> None:
    now = datetime.now(UTC)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in candidate_models:
        val = str(raw).strip()
        if not val:
            continue
        if val in seen:
            continue
        normalized.append(val)
        seen.add(val)

    if not normalized or winner_model not in seen:
        return

    existing = db.execute(
        select(BanditArmStats).where(
            BanditArmStats.api_key_id == project_id,
            BanditArmStats.assistant_id == assistant_id,
            BanditArmStats.context_key == context_key,
            BanditArmStats.arm_logical_model.in_(normalized),
        )
    ).scalars().all()
    by_arm = {row.arm_logical_model: row for row in existing}

    for arm in normalized:
        row = by_arm.get(arm)
        if row is None:
            row = BanditArmStats(
                api_key_id=project_id,
                assistant_id=assistant_id,
                context_key=context_key,
                arm_logical_model=arm,
                alpha=1.0,
                beta=1.0,
                wins=0,
                losses=0,
                samples=0,
                last_updated_at=None,
            )
            db.add(row)
            by_arm[arm] = row

        row.samples = int(row.samples or 0) + 1
        row.last_updated_at = now
        if arm == winner_model:
            row.alpha = float(row.alpha or 1.0) + 1.0
            row.wins = int(row.wins or 0) + 1
        else:
            row.beta = float(row.beta or 1.0) + 1.0
            row.losses = int(row.losses or 0) + 1
    # 由调用方统一 commit，避免在同一事务中产生意外提交。


__all__ = [
    "BanditRecommendation",
    "CandidateScore",
    "apply_winner_update",
    "build_context_features",
    "build_context_key",
    "recommend_challengers",
]
