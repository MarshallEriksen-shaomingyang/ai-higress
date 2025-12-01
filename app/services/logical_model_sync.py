"""
逻辑模型写入 Redis 的通用同步工具。

- collect_logical_models: 从数据库读取 provider_models + providers 聚合出 LogicalModel。
- sync_logical_models_to_redis: 将 LogicalModel 批量写入 llm:logical:{logical_model}。
- sync_logical_models: 组合型入口，便于在创建提供商/模型后直接刷新 Redis，后续也可被 Celery 定时任务复用。
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.db.session import SessionLocal
from app.logging_config import logger
from app.models import Provider, ProviderModel
from app.schemas.logical_model import LogicalModel, PhysicalModel
from app.schemas.model import ModelCapability
from app.storage.redis_service import (
    delete_logical_model,
    list_logical_models,
    set_logical_model,
)


def _normalize_capabilities(raw: Iterable[object] | None) -> list[ModelCapability]:
    caps: list[ModelCapability] = []
    if raw is None:
        return caps

    for item in raw:
        try:
            caps.append(ModelCapability(str(item)))
        except ValueError:
            logger.warning("忽略未知的模型能力值: %r", item)
    return caps


def _dedup_capabilities(caps: Iterable[ModelCapability]) -> list[ModelCapability]:
    seen: set[ModelCapability] = set()
    ordered: list[ModelCapability] = []
    for cap in caps:
        if cap in seen:
            continue
        seen.add(cap)
        ordered.append(cap)
    return ordered


def _build_endpoint(provider: Provider) -> str:
    base = str(provider.base_url).rstrip("/")
    transport = (provider.transport or "http").lower()
    if transport == "sdk":
        return base

    path = (provider.messages_path or "/v1/chat/completions").strip()
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def collect_logical_models(
    *,
    session: Session | None = None,
    provider_ids: Sequence[str] | None = None,
) -> list[LogicalModel]:
    """
    从数据库读取 provider_models & providers，按 model_id 聚合 LogicalModel。

    当传入 provider_ids 时，只同步指定提供商（基于 provider.provider_id）。
    """

    owns_session = False
    if session is None:
        session = SessionLocal()
        owns_session = True

    try:
        stmt = select(ProviderModel, Provider).join(Provider, Provider.id == ProviderModel.provider_id)
        if provider_ids:
            stmt = stmt.where(Provider.provider_id.in_(provider_ids))
        rows = session.execute(stmt).all()
    finally:
        if owns_session:
            session.close()

    upstreams_by_logical: dict[str, list[PhysicalModel]] = defaultdict(list)
    caps_by_logical: dict[str, set[ModelCapability]] = defaultdict(set)
    display_by_logical: dict[str, str] = {}
    now = time.time()

    for provider_model, provider in rows:
        caps = _normalize_capabilities(provider_model.capabilities)
        caps_by_logical[provider_model.model_id].update(caps)
        display_by_logical.setdefault(
            provider_model.model_id, provider_model.display_name or provider_model.model_id
        )

        updated_at = provider_model.updated_at.timestamp() if provider_model.updated_at else now
        upstreams_by_logical[provider_model.model_id].append(
            PhysicalModel(
                provider_id=provider.provider_id,
                model_id=provider_model.model_id,
                endpoint=_build_endpoint(provider),
                base_weight=provider.weight or 1.0,
                region=provider.region,
                max_qps=provider.max_qps,
                meta_hash=provider_model.meta_hash,
                updated_at=updated_at,
            )
        )

    logical_models: list[LogicalModel] = []
    for logical_id, upstreams in upstreams_by_logical.items():
        caps = list(caps_by_logical.get(logical_id) or [])
        latest = max((up.updated_at for up in upstreams), default=now)
        logical_models.append(
            LogicalModel(
                logical_id=logical_id,
                display_name=display_by_logical.get(logical_id, logical_id),
                description=f"Auto-generated logical model for '{logical_id}'",
                capabilities=caps or [ModelCapability.CHAT],
                upstreams=upstreams,
                enabled=True,
                updated_at=latest,
            )
        )

    return logical_models


async def sync_logical_models_to_redis(
    redis: Redis, logical_models: Iterable[LogicalModel]
) -> int:
    """
    将 LogicalModel 批量写入 Redis，返回写入数量。
    """

    count = 0
    for logical in logical_models:
        await set_logical_model(redis, logical)
        count += 1
    return count


async def sync_logical_models(
    redis: Redis,
    *,
    session: Session | None = None,
    provider_ids: Sequence[str] | None = None,
) -> list[LogicalModel]:
    """
    组合型入口：从数据库聚合并写入 Redis，便于在创建提供商/模型后直接调用。
    """

    logical_models = collect_logical_models(session=session, provider_ids=provider_ids)
    provider_set = set(provider_ids) if provider_ids else None

    existing_models: list[LogicalModel] = []
    if provider_set is not None:
        # 增量刷新需要读取现有键，避免覆盖其它提供商的上游。
        existing_models = await list_logical_models(redis)

    merged_models: list[LogicalModel] = []
    logical_ids: set[str] = set()
    now = time.time()

    if provider_set is not None:
        existing_map = {model.logical_id: model for model in existing_models}
        for logical in logical_models:
            logical_ids.add(logical.logical_id)
            if logical.logical_id in existing_map:
                base = existing_map[logical.logical_id]
                preserved_upstreams = [
                    up for up in base.upstreams if up.provider_id not in provider_set
                ]
                merged_upstreams = preserved_upstreams + logical.upstreams
                merged_caps = _dedup_capabilities(
                    list(base.capabilities) + list(logical.capabilities)
                )
                merged_updated_at = max(
                    [up.updated_at for up in merged_upstreams] + [base.updated_at, now]
                )
                merged_models.append(
                    base.model_copy(
                        update={
                            "capabilities": merged_caps,
                            "upstreams": merged_upstreams,
                            "display_name": logical.display_name or base.display_name,
                            "description": logical.description or base.description,
                            "enabled": logical.enabled and base.enabled,
                            "updated_at": merged_updated_at,
                        }
                    )
                )
            else:
                merged_models.append(logical)

        stale_logical_ids: list[str] = []
        for existing in existing_models:
            if existing.logical_id in logical_ids:
                continue
            has_affected = any(up.provider_id in provider_set for up in existing.upstreams)
            if not has_affected:
                continue
            remaining_upstreams = [
                up for up in existing.upstreams if up.provider_id not in provider_set
            ]
            if remaining_upstreams:
                merged_models.append(
                    existing.model_copy(
                        update={
                            "upstreams": remaining_upstreams,
                            "updated_at": max(up.updated_at for up in remaining_upstreams),
                        }
                    )
                )
            else:
                stale_logical_ids.append(existing.logical_id)

        if merged_models:
            await sync_logical_models_to_redis(redis, merged_models)
        for stale_id in stale_logical_ids:
            await delete_logical_model(redis, stale_id)
        return merged_models

    # 全量刷新：写入最新数据，并删除数据库中已不存在的逻辑模型。
    if logical_models:
        await sync_logical_models_to_redis(redis, logical_models)

    existing_models = await list_logical_models(redis)
    existing_ids = {model.logical_id for model in existing_models}
    current_ids = {model.logical_id for model in logical_models}
    stale_ids = existing_ids - current_ids
    for stale_id in stale_ids:
        await delete_logical_model(redis, stale_id)

    return logical_models


__all__ = [
    "collect_logical_models",
    "sync_logical_models",
    "sync_logical_models_to_redis",
]
