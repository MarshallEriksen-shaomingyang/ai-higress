from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.jwt_auth import AuthenticatedUser
from app.repositories.api_key_repository import persist_api_key as repo_persist_api_key
from app.schemas import ProjectChatSettingsResponse, ProjectChatSettingsUpdateRequest
from app.services.project_eval_config_service import resolve_project_context

DEFAULT_PROJECT_CHAT_MODEL = "auto"


def _normalize_optional_model(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return raw


def get_project_chat_settings(
    db: Session,
    *,
    project_id: UUID,
    current_user: AuthenticatedUser,
) -> ProjectChatSettingsResponse:
    ctx = resolve_project_context(db, project_id=project_id, current_user=current_user)
    api_key = ctx.api_key
    return ProjectChatSettingsResponse(
        project_id=ctx.project_id,
        default_logical_model=_normalize_optional_model(getattr(api_key, "chat_default_logical_model", None))
        or DEFAULT_PROJECT_CHAT_MODEL,
        title_logical_model=_normalize_optional_model(getattr(api_key, "chat_title_logical_model", None)),
    )


def update_project_chat_settings(
    db: Session,
    *,
    project_id: UUID,
    current_user: AuthenticatedUser,
    payload: ProjectChatSettingsUpdateRequest,
) -> ProjectChatSettingsResponse:
    ctx = resolve_project_context(db, project_id=project_id, current_user=current_user)
    api_key = ctx.api_key

    if "default_logical_model" in payload.model_fields_set:
        api_key.chat_default_logical_model = _normalize_optional_model(payload.default_logical_model)
    if "title_logical_model" in payload.model_fields_set:
        api_key.chat_title_logical_model = _normalize_optional_model(payload.title_logical_model)

    repo_persist_api_key(db, api_key=api_key, allowed_provider_ids=None)

    return get_project_chat_settings(db, project_id=project_id, current_user=current_user)


__all__ = [
    "DEFAULT_PROJECT_CHAT_MODEL",
    "get_project_chat_settings",
    "update_project_chat_settings",
]
