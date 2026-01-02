from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.auth import AuthenticatedAPIKey
from app.deps import get_db, get_http_client, get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas.memory_route import ProjectMemoryRouteDryRunRequest, ProjectMemoryRouteDryRunResponse
from app.services.chat_memory_router import route_chat_memory_with_raw
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
    resolve_project_context,
)

router = APIRouter(tags=["memory"], dependencies=[Depends(require_jwt_token)])
memory_debug_logger = logging.getLogger("apiproxy.memory_debug")


def _preview_text(value: str | None, *, limit: int = 200) -> str:
    text = (value or "").strip().replace("\r", " ").replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _to_authenticated_api_key(*, api_key, current_user: AuthenticatedUser) -> AuthenticatedAPIKey:
    return AuthenticatedAPIKey(
        id=UUID(str(api_key.id)),
        user_id=UUID(str(api_key.user_id)),
        user_username=str(current_user.username or ""),
        is_superuser=bool(current_user.is_superuser),
        name=str(getattr(api_key, "name", "") or ""),
        is_active=bool(getattr(api_key, "is_active", True)),
        disabled_reason=getattr(api_key, "disabled_reason", None),
        has_provider_restrictions=bool(getattr(api_key, "has_provider_restrictions", False)),
        allowed_provider_ids=list(getattr(api_key, "allowed_provider_ids", None) or []),
    )


@router.post(
    "/v1/projects/{project_id}/memory-route/dry-run",
    response_model=ProjectMemoryRouteDryRunResponse,
)
async def dry_run_project_memory_route(
    project_id: UUID,
    payload: ProjectMemoryRouteDryRunRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client=Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> ProjectMemoryRouteDryRunResponse:
    ctx = resolve_project_context(db, project_id=project_id, current_user=current_user)

    router_model = (payload.router_logical_model or getattr(ctx.api_key, "kb_memory_router_logical_model", None) or "").strip()
    if not router_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="kb_memory_router_logical_model 未配置，请先在项目聊天设置中设置或在请求里显式传入 router_logical_model",
        )
    if router_model == "auto":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="memory-route 暂不支持 router_logical_model=auto，请设置一个明确的逻辑模型",
        )

    cfg = get_or_default_project_eval_config(db, project_id=UUID(str(ctx.api_key.id)))
    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )

    auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)

    decision, raw = await route_chat_memory_with_raw(
        db,
        redis=redis,
        client=client,
        api_key=auth_key,
        effective_provider_ids=effective_provider_ids,
        router_logical_model=router_model,
        transcript=payload.transcript,
        idempotency_key=f"mem_route_dry:{project_id}",
    )

    if memory_debug_logger.isEnabledFor(logging.DEBUG):
        memory_debug_logger.debug(
            "memory_route_dry_run: ok (project_id=%s user_id=%s router_model=%s transcript_chars=%s should_store=%s scope=%s items=%s memory_preview=%s raw_chars=%s)",
            str(project_id),
            str(current_user.id),
            router_model,
            len(payload.transcript or ""),
            bool(decision.should_store),
            str(decision.scope),
            len(decision.memory_items or []),
            _preview_text(decision.memory_text, limit=160),
            len(raw or ""),
        )

    return ProjectMemoryRouteDryRunResponse(
        project_id=UUID(str(ctx.project_id)),
        router_logical_model=router_model,
        should_store=bool(decision.should_store),
        scope=decision.scope,
        memory_text=decision.memory_text,
        memory_items=decision.memory_items or [],
        structured_ops=getattr(decision, "structured_ops", None) or [],
        raw_model_output=raw,
    )


__all__ = ["router"]
