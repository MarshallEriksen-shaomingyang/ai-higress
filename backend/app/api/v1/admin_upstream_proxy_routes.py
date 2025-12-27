from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.deps import get_db, get_redis
from app.errors import bad_request, forbidden, not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import UpstreamProxyConfig, UpstreamProxyEndpoint, UpstreamProxySource
from app.repositories.upstream_proxy_repository import get_or_create_proxy_config, upsert_endpoints
from app.schemas import (
    UpstreamProxyConfigResponse,
    UpstreamProxyConfigUpdateRequest,
    UpstreamProxyEndpointCreateRequest,
    UpstreamProxyEndpointResponse,
    UpstreamProxyEndpointsResponse,
    UpstreamProxyEndpointUpdateRequest,
    UpstreamProxyImportRequest,
    UpstreamProxyImportResponse,
    UpstreamProxySourceCreateRequest,
    UpstreamProxySourceResponse,
    UpstreamProxySourcesResponse,
    UpstreamProxySourceUpdateRequest,
    UpstreamProxyStatusResponse,
    UpstreamProxyTaskResponse,
)
from app.services.encryption import encrypt_secret
from app.services.upstream_proxy.redis import clear_runtime_pool, set_runtime_config
from app.services.upstream_proxy.secrets import set_source_remote_headers, set_source_remote_url
from app.services.upstream_proxy.utils import ParsedProxy, normalize_scheme, parse_proxy_line, split_proxy_text

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = Any  # type: ignore[misc,assignment]

router = APIRouter(tags=["admin-upstream-proxy"], dependencies=[Depends(require_jwt_token)])


def _ensure_admin(current_user: AuthenticatedUser) -> None:
    if not current_user.is_superuser:
        raise forbidden("需要管理员权限")

def _to_source_response(source: UpstreamProxySource) -> UpstreamProxySourceResponse:
    remote_url_masked = None
    if source.remote_url_encrypted:
        # Do not attempt to decrypt (may embed tokens). Only indicate presence.
        remote_url_masked = "***"
    remote_headers_masked = None
    if source.remote_headers_encrypted:
        remote_headers_masked = {"***": "***"}
    return UpstreamProxySourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        enabled=bool(source.enabled),
        default_scheme=source.default_scheme,
        refresh_interval_seconds=source.refresh_interval_seconds,
        last_refresh_at=source.last_refresh_at,
        last_refresh_error=source.last_refresh_error,
        remote_url_masked=remote_url_masked,
        remote_headers_masked=remote_headers_masked,
        healthcheck_url=source.healthcheck_url,
        healthcheck_timeout_ms=source.healthcheck_timeout_ms,
        healthcheck_method=source.healthcheck_method,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _to_endpoint_response(endpoint: UpstreamProxyEndpoint) -> UpstreamProxyEndpointResponse:
    return UpstreamProxyEndpointResponse(
        id=endpoint.id,
        source_id=endpoint.source_id,  # type: ignore[arg-type]
        scheme=endpoint.scheme,
        host=endpoint.host,
        port=int(endpoint.port),
        username=endpoint.username,
        has_password=bool(endpoint.password_encrypted),
        enabled=bool(endpoint.enabled),
        last_seen_at=endpoint.last_seen_at,
        last_check_at=endpoint.last_check_at,
        last_ok=endpoint.last_ok,
        last_latency_ms=endpoint.last_latency_ms,
        consecutive_failures=int(endpoint.consecutive_failures or 0),
        last_error=endpoint.last_error,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


async def _sync_config_to_redis(redis: Redis, cfg: UpstreamProxyConfig) -> None:
    await set_runtime_config(
        redis,
        enabled=bool(cfg.enabled),
        failure_cooldown_seconds=int(cfg.failure_cooldown_seconds),
    )
    if not cfg.enabled:
        await clear_runtime_pool(redis)


@router.get("/admin/upstream-proxy/config", response_model=UpstreamProxyConfigResponse)
async def get_upstream_proxy_config(
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyConfigResponse:
    _ensure_admin(current_user)
    cfg = get_or_create_proxy_config(db)
    await _sync_config_to_redis(redis, cfg)
    return UpstreamProxyConfigResponse.model_validate(cfg, from_attributes=True)


@router.put("/admin/upstream-proxy/config", response_model=UpstreamProxyConfigResponse)
async def update_upstream_proxy_config(
    payload: UpstreamProxyConfigUpdateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyConfigResponse:
    _ensure_admin(current_user)
    cfg = get_or_create_proxy_config(db)

    if payload.enabled is not None:
        cfg.enabled = payload.enabled
    if payload.selection_strategy is not None:
        cfg.selection_strategy = payload.selection_strategy
    if payload.failure_cooldown_seconds is not None:
        cfg.failure_cooldown_seconds = payload.failure_cooldown_seconds
    if payload.healthcheck_url is not None:
        cfg.healthcheck_url = payload.healthcheck_url
    if payload.healthcheck_timeout_ms is not None:
        cfg.healthcheck_timeout_ms = payload.healthcheck_timeout_ms
    if payload.healthcheck_method is not None:
        cfg.healthcheck_method = payload.healthcheck_method
    if payload.healthcheck_interval_seconds is not None:
        cfg.healthcheck_interval_seconds = payload.healthcheck_interval_seconds

    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    await _sync_config_to_redis(redis, cfg)
    return UpstreamProxyConfigResponse.model_validate(cfg, from_attributes=True)


@router.get("/admin/upstream-proxy/sources", response_model=UpstreamProxySourcesResponse)
def list_upstream_proxy_sources(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxySourcesResponse:
    _ensure_admin(current_user)
    stmt: Select[tuple[UpstreamProxySource]] = select(UpstreamProxySource).order_by(UpstreamProxySource.created_at.desc())
    sources = list(db.execute(stmt).scalars().all())
    return UpstreamProxySourcesResponse(sources=[_to_source_response(s) for s in sources], total=len(sources))


@router.post("/admin/upstream-proxy/sources", response_model=UpstreamProxySourceResponse)
def create_upstream_proxy_source(
    payload: UpstreamProxySourceCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxySourceResponse:
    _ensure_admin(current_user)
    if payload.source_type not in {"static_list", "remote_text_list"}:
        raise bad_request("source_type 仅支持 static_list / remote_text_list")
    default_scheme = normalize_scheme(payload.default_scheme)

    source = UpstreamProxySource(
        name=payload.name,
        source_type=payload.source_type,
        enabled=payload.enabled,
        default_scheme=default_scheme,
        refresh_interval_seconds=payload.refresh_interval_seconds,
        healthcheck_url=payload.healthcheck_url,
        healthcheck_timeout_ms=payload.healthcheck_timeout_ms,
        healthcheck_method=payload.healthcheck_method,
    )
    if payload.remote_url:
        set_source_remote_url(source, payload.remote_url)
    if payload.remote_headers is not None:
        set_source_remote_headers(source, payload.remote_headers)

    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_source_response(source)


@router.put("/admin/upstream-proxy/sources/{source_id}", response_model=UpstreamProxySourceResponse)
def update_upstream_proxy_source(
    source_id: UUID,
    payload: UpstreamProxySourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxySourceResponse:
    _ensure_admin(current_user)
    source = db.execute(select(UpstreamProxySource).where(UpstreamProxySource.id == source_id)).scalars().first()
    if source is None:
        raise not_found("代理来源不存在")

    if payload.name is not None:
        source.name = payload.name
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.default_scheme is not None:
        source.default_scheme = normalize_scheme(payload.default_scheme)
    if payload.refresh_interval_seconds is not None:
        source.refresh_interval_seconds = payload.refresh_interval_seconds

    if payload.remote_url is not None:
        set_source_remote_url(source, payload.remote_url)
    if payload.remote_headers is not None:
        set_source_remote_headers(source, payload.remote_headers)

    if payload.healthcheck_url is not None:
        source.healthcheck_url = payload.healthcheck_url
    if payload.healthcheck_timeout_ms is not None:
        source.healthcheck_timeout_ms = payload.healthcheck_timeout_ms
    if payload.healthcheck_method is not None:
        source.healthcheck_method = payload.healthcheck_method

    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_source_response(source)


@router.delete("/admin/upstream-proxy/sources/{source_id}")
def delete_upstream_proxy_source(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict[str, Any]:
    _ensure_admin(current_user)
    source = db.execute(select(UpstreamProxySource).where(UpstreamProxySource.id == source_id)).scalars().first()
    if source is None:
        raise not_found("代理来源不存在")
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.get("/admin/upstream-proxy/endpoints", response_model=UpstreamProxyEndpointsResponse)
def list_upstream_proxy_endpoints(
    source_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyEndpointsResponse:
    _ensure_admin(current_user)
    stmt: Select[tuple[UpstreamProxyEndpoint]] = select(UpstreamProxyEndpoint).order_by(
        UpstreamProxyEndpoint.created_at.desc()
    )
    if source_id is not None:
        stmt = stmt.where(UpstreamProxyEndpoint.source_id == source_id)
    endpoints = list(db.execute(stmt).scalars().all())
    return UpstreamProxyEndpointsResponse(
        endpoints=[_to_endpoint_response(e) for e in endpoints],
        total=len(endpoints),
    )


@router.post("/admin/upstream-proxy/endpoints", response_model=UpstreamProxyEndpointResponse)
def create_upstream_proxy_endpoint(
    payload: UpstreamProxyEndpointCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyEndpointResponse:
    _ensure_admin(current_user)
    source = db.execute(select(UpstreamProxySource).where(UpstreamProxySource.id == payload.source_id)).scalars().first()
    if source is None:
        raise not_found("代理来源不存在")

    scheme = normalize_scheme(payload.scheme)
    parsed = ParsedProxy(
        scheme=scheme,
        host=payload.host,
        port=int(payload.port),
        username=payload.username,
        password=payload.password,
    )
    # Reuse upsert path for consistent identity hashing.
    upsert_endpoints(db, source=source, proxies=[parsed], mark_seen=False)
    db.commit()

    # Fetch the endpoint back.
    # We locate by identity_hash computed in upsert_endpoints, so reconstruct via parsing.
    from app.services.upstream_proxy.utils import compute_identity_hash

    identity_hash = compute_identity_hash(
        scheme=scheme,
        host=payload.host,
        port=int(payload.port),
        username=payload.username,
    )
    endpoint = (
        db.execute(
            select(UpstreamProxyEndpoint).where(
                UpstreamProxyEndpoint.source_id == source.id,
                UpstreamProxyEndpoint.identity_hash == identity_hash,
            )
        )
        .scalars()
        .first()
    )
    if endpoint is None:
        raise bad_request("创建代理失败")
    endpoint.enabled = payload.enabled
    if payload.password:
        endpoint.password_encrypted = encrypt_secret(payload.password)
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)


@router.put("/admin/upstream-proxy/endpoints/{endpoint_id}", response_model=UpstreamProxyEndpointResponse)
def update_upstream_proxy_endpoint(
    endpoint_id: UUID,
    payload: UpstreamProxyEndpointUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyEndpointResponse:
    _ensure_admin(current_user)
    endpoint = db.execute(select(UpstreamProxyEndpoint).where(UpstreamProxyEndpoint.id == endpoint_id)).scalars().first()
    if endpoint is None:
        raise not_found("代理条目不存在")
    if payload.enabled is not None:
        endpoint.enabled = payload.enabled
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)


@router.delete("/admin/upstream-proxy/endpoints/{endpoint_id}")
def delete_upstream_proxy_endpoint(
    endpoint_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> dict[str, Any]:
    _ensure_admin(current_user)
    endpoint = db.execute(select(UpstreamProxyEndpoint).where(UpstreamProxyEndpoint.id == endpoint_id)).scalars().first()
    if endpoint is None:
        raise not_found("代理条目不存在")
    db.delete(endpoint)
    db.commit()
    return {"ok": True}


@router.post("/admin/upstream-proxy/endpoints/import", response_model=UpstreamProxyImportResponse)
def import_upstream_proxy_endpoints(
    payload: UpstreamProxyImportRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyImportResponse:
    _ensure_admin(current_user)
    source = db.execute(select(UpstreamProxySource).where(UpstreamProxySource.id == payload.source_id)).scalars().first()
    if source is None:
        raise not_found("代理来源不存在")

    default_scheme = normalize_scheme(payload.default_scheme or source.default_scheme)
    lines = split_proxy_text(payload.text)
    parsed: list[ParsedProxy] = []
    for line in lines:
        try:
            parsed.append(parse_proxy_line(line, default_scheme=default_scheme))
        except Exception:
            continue
    inserted_or_updated = upsert_endpoints(db, source=source, proxies=parsed, mark_seen=False)
    db.commit()
    return UpstreamProxyImportResponse(inserted_or_updated=inserted_or_updated)


@router.post("/admin/upstream-proxy/tasks/refresh", response_model=UpstreamProxyTaskResponse)
def trigger_upstream_proxy_refresh(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyTaskResponse:
    _ensure_admin(current_user)
    res = celery_app.send_task("tasks.upstream_proxy.refresh_sources")
    return UpstreamProxyTaskResponse(task_id=res.id)


@router.post("/admin/upstream-proxy/tasks/check", response_model=UpstreamProxyTaskResponse)
def trigger_upstream_proxy_health_check(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyTaskResponse:
    _ensure_admin(current_user)
    res = celery_app.send_task("tasks.upstream_proxy.check_health")
    return UpstreamProxyTaskResponse(task_id=res.id)


@router.get("/admin/upstream-proxy/status", response_model=UpstreamProxyStatusResponse)
async def upstream_proxy_status(
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UpstreamProxyStatusResponse:
    _ensure_admin(current_user)
    cfg = get_or_create_proxy_config(db)
    await _sync_config_to_redis(redis, cfg)

    total_sources = db.execute(select(func.count(UpstreamProxySource.id))).scalar_one()
    total_endpoints = db.execute(select(func.count(UpstreamProxyEndpoint.id))).scalar_one()
    try:
        available_endpoints = int(await redis.scard("upstream_proxy:available"))
    except Exception:
        available_endpoints = 0
    return UpstreamProxyStatusResponse(
        config_enabled=bool(cfg.enabled),
        total_sources=int(total_sources),
        total_endpoints=int(total_endpoints),
        available_endpoints=available_endpoints,
    )


__all__ = ["router"]
