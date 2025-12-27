from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser
from app.models import APIKey, ProjectEvalConfig
from app.repositories.project_eval_config_repository import (
    get_project_eval_config as repo_get_project_eval_config,
    persist_project_eval_config as repo_persist_project_eval_config,
)
from app.repositories.provider_repository import (
    list_private_provider_ids_for_user,
    list_public_provider_ids,
    list_shared_provider_ids_for_user,
    provider_id_exists,
)
from app.services.api_key_service import get_api_key_by_id

ALLOWED_PROVIDER_SCOPES = {"private", "shared", "public"}
DEFAULT_PROVIDER_SCOPES = ["private", "shared", "public"]


@dataclass(frozen=True)
class ResolvedProjectContext:
    project_id: UUID
    api_key: APIKey


def resolve_project_context(
    db: Session,
    *,
    project_id: UUID | str,
    current_user: AuthenticatedUser,
) -> ResolvedProjectContext:
    """
    解析项目上下文（MVP: project_id == api_key_id）并校验权限。
    """
    api_key = get_api_key_by_id(db, project_id)
    if api_key is None:
        raise not_found("项目不存在或无权访问", details={"project_id": str(project_id)})

    if not bool(current_user.is_superuser) and str(api_key.user_id) != str(current_user.id):
        raise forbidden("无权访问该项目", details={"project_id": str(project_id)})

    return ResolvedProjectContext(project_id=UUID(str(api_key.id)), api_key=api_key)


def get_or_default_project_eval_config(
    db: Session,
    *,
    project_id: UUID,
) -> ProjectEvalConfig:
    cfg = repo_get_project_eval_config(db, project_id=project_id)
    if cfg is not None:
        return cfg

    # 返回未持久化的默认配置对象（用于读接口）。
    return ProjectEvalConfig(
        api_key_id=project_id,
        enabled=True,
        max_challengers=2,
        provider_scopes=DEFAULT_PROVIDER_SCOPES,
        candidate_logical_models=None,
        cooldown_seconds=120,
        budget_per_eval_credits=None,
        rubric=None,
        project_ai_enabled=False,
        project_ai_provider_model=None,
    )


def _normalize_provider_scopes(scopes: list[str] | None) -> list[str] | None:
    if scopes is None:
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in scopes:
        val = str(raw).strip().lower()
        if not val:
            continue
        if val not in ALLOWED_PROVIDER_SCOPES:
            raise bad_request(
                "非法的 provider_scopes",
                details={"allowed": sorted(ALLOWED_PROVIDER_SCOPES), "got": scopes},
            )
        if val in seen:
            continue
        normalized.append(val)
        seen.add(val)
    if not normalized:
        raise bad_request("provider_scopes 不能为空", details={"got": scopes})
    return normalized


def upsert_project_eval_config(
    db: Session,
    *,
    project_id: UUID,
    enabled: bool | None = None,
    max_challengers: int | None = None,
    provider_scopes: list[str] | None = None,
    candidate_logical_models: list[str] | None = None,
    cooldown_seconds: int | None = None,
    budget_per_eval_credits: int | None = None,
    rubric: str | None = None,
    project_ai_enabled: bool | None = None,
    project_ai_provider_model: str | None = None,
) -> ProjectEvalConfig:
    cfg = repo_get_project_eval_config(db, project_id=project_id)
    if cfg is None:
        cfg = ProjectEvalConfig(api_key_id=project_id)

    if enabled is not None:
        cfg.enabled = bool(enabled)
    if max_challengers is not None:
        if max_challengers < 0 or max_challengers > 5:
            raise bad_request("max_challengers 超出范围", details={"max_challengers": max_challengers})
        cfg.max_challengers = int(max_challengers)
    normalized_scopes = _normalize_provider_scopes(provider_scopes)
    if normalized_scopes is not None:
        cfg.provider_scopes = normalized_scopes
    if candidate_logical_models is not None:
        if candidate_logical_models and len(candidate_logical_models) > 200:
            raise bad_request("candidate_logical_models 过多", details={"count": len(candidate_logical_models)})
        cfg.candidate_logical_models = candidate_logical_models
    if cooldown_seconds is not None:
        if cooldown_seconds < 0 or cooldown_seconds > 24 * 3600:
            raise bad_request("cooldown_seconds 超出范围", details={"cooldown_seconds": cooldown_seconds})
        cfg.cooldown_seconds = int(cooldown_seconds)
    if budget_per_eval_credits is not None:
        if budget_per_eval_credits < 0:
            raise bad_request("budget_per_eval_credits 不能为负数")
        cfg.budget_per_eval_credits = int(budget_per_eval_credits)
    if rubric is not None:
        cfg.rubric = rubric
    if project_ai_enabled is not None:
        cfg.project_ai_enabled = bool(project_ai_enabled)
    if project_ai_provider_model is not None:
        raw = str(project_ai_provider_model).strip()
        if not raw:
            cfg.project_ai_provider_model = None
        else:
            if "/" not in raw:
                raise bad_request(
                    "project_ai_provider_model 格式非法，应为 'provider_id/model_id'",
                    details={"project_ai_provider_model": raw},
                )
            provider_id, model_id = raw.split("/", 1)
            provider_id = provider_id.strip()
            model_id = model_id.strip()
            if not provider_id or not model_id:
                raise bad_request(
                    "project_ai_provider_model 格式非法，应为 'provider_id/model_id'",
                    details={"project_ai_provider_model": raw},
                )
            if not provider_id_exists(db, provider_id=provider_id):
                raise bad_request(
                    "project_ai_provider_model 的 provider_id 不存在",
                    details={"provider_id": provider_id},
                )
            cfg.project_ai_provider_model = f"{provider_id}/{model_id}"

    return repo_persist_project_eval_config(db, cfg=cfg)


def get_effective_provider_ids_for_user(
    db: Session,
    *,
    user_id: UUID,
    api_key: APIKey,
    provider_scopes: list[str] | None,
) -> set[str]:
    """
    计算评测/聊天执行时可用的 provider_id 集合：
    - 用户可访问 provider（自有/分享/公共）
    - 受 provider_scopes（private/shared/public）约束
    - 再与 API Key 的 allowed_provider_ids 取交集（若启用限制）
    """
    scopes = provider_scopes or DEFAULT_PROVIDER_SCOPES
    normalized = _normalize_provider_scopes(scopes) or DEFAULT_PROVIDER_SCOPES

    # public
    public_ids = list_public_provider_ids(db)
    # private（包含用户自己的 restricted/private）
    private_ids = list_private_provider_ids_for_user(db, user_id=user_id)
    # shared（他人分享给我：restricted + link + owner != me）
    shared_ids = list_shared_provider_ids_for_user(db, user_id=user_id)

    union: set[str] = set()
    if "public" in normalized:
        union |= public_ids
    if "private" in normalized:
        union |= private_ids
    if "shared" in normalized:
        union |= shared_ids

    if api_key.has_provider_restrictions:
        allowed = {pid for pid in api_key.allowed_provider_ids if pid}
        union &= allowed

    if not union:
        raise forbidden(
            "当前项目下无可用的提供商",
            details={"project_id": str(api_key.id)},
        )

    return union


__all__ = [
    "DEFAULT_PROVIDER_SCOPES",
    "ResolvedProjectContext",
    "get_effective_provider_ids_for_user",
    "get_or_default_project_eval_config",
    "resolve_project_context",
    "upsert_project_eval_config",
]
