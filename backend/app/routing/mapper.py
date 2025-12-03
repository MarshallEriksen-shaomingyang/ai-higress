"""
Logical model mapping and consistency checks.

This module focuses on mapping logical models to physical upstream
models and verifying that upstreams are consistent with the underlying
provider models as described in specs/001-model-routing/research.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.schemas import LogicalModel, Model, PhysicalModel


@dataclass
class ConsistencyIssue:
    """
    Single consistency issue for a logical model mapping.
    """

    level: str  # "error" or "warning"
    code: str
    message: str


def build_provider_model_index(models: Iterable[Model]) -> dict[tuple[str, str], Model]:
    """
    Build a lookup index (provider_id, model_id) -> Model.
    """
    index: dict[tuple[str, str], Model] = {}
    for m in models:
        index[(m.provider_id, m.model_id)] = m
    return index


def validate_logical_model_consistency(
    logical_model: LogicalModel,
    provider_models: dict[tuple[str, str], Model],
) -> list[ConsistencyIssue]:
    """
    Validate that all upstream physical models referenced by a LogicalModel
    are compatible and exist in the provider-model catalogue.

    Current checks (can be extended later):
    - Every (provider_id, model_id) in upstreams must exist in provider_models
    - If upstream provider models expose `meta_hash`, conflicting hashes
      are treated as an error
    - When meta_hash is missing or identical, but model families differ,
      we emit a warning (potentially different base model)
    """
    issues: list[ConsistencyIssue] = []

    # 1) Existence check.
    present_models: list[Model] = []
    for upstream in logical_model.upstreams:
        key = (upstream.provider_id, upstream.model_id)
        if key not in provider_models:
            issues.append(
                ConsistencyIssue(
                    level="error",
                    code="missing_provider_model",
                    message=(
                        f"Upstream ({upstream.provider_id}, {upstream.model_id}) "
                        f"not found in provider model catalogue"
                    ),
                )
            )
        else:
            present_models.append(provider_models[key])

    if not present_models:
        # Nothing else to validate if no upstreams resolved.
        return issues

    # 2) meta_hash consistency (strongest signal when present).
    hashes = {m.meta_hash for m in present_models if m.meta_hash}
    if len(hashes) > 1:
        issues.append(
            ConsistencyIssue(
                level="error",
                code="meta_hash_mismatch",
                message=f"Logical model {logical_model.logical_id} "
                f"maps to upstreams with conflicting meta_hash values: {sorted(hashes)}",
            )
        )
        # When hash conflicts exist, we do not attempt further inference.
        return issues

    # 3) Family mismatch warning (weaker signal).
    families = {m.family for m in present_models}
    if len(families) > 1:
        issues.append(
            ConsistencyIssue(
                level="warning",
                code="family_mismatch",
                message=f"Logical model {logical_model.logical_id} maps to different "
                f"model families: {sorted(families)}",
            )
        )

    return issues


def is_logical_model_consistent(
    logical_model: LogicalModel,
    provider_models: dict[tuple[str, str], Model],
) -> bool:
    """
    Convenience wrapper that returns True when no *errors* are present.
    Warnings are ignored for this boolean check.
    """
    issues = validate_logical_model_consistency(logical_model, provider_models)
    return all(issue.level != "error" for issue in issues)


def select_candidate_upstreams(
    logical_model: LogicalModel,
    *,
    preferred_region: str | None = None,
    exclude_providers: Sequence[str] | None = None,
) -> list[PhysicalModel]:
    """
    Return candidate upstreams for a logical model, filtered by optional
    constraints such as preferred region or excluded provider ids.

    This function does not apply any scoring; it simply filters the
    logical model's upstream list. Scoring and final selection belong
    to the scheduler (User Story 3).
    """
    exclude_set = set(exclude_providers or [])

    def _eligible(up: PhysicalModel) -> bool:
        if up.provider_id in exclude_set:
            return False
        return True

    upstreams = [up for up in logical_model.upstreams if _eligible(up)]

    if preferred_region:
        region_matches = [
            up for up in upstreams if (up.region or "").lower() == preferred_region.lower()
        ]
        if region_matches:
            return region_matches

    return upstreams


__all__ = [
    "ConsistencyIssue",
    "build_provider_model_index",
    "is_logical_model_consistent",
    "select_candidate_upstreams",
    "validate_logical_model_consistency",
]

