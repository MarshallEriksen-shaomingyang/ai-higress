"""
Provider configuration loader backed by database records.

All provider metadata (base URLs, weights, static models, API keys, etc.)
is stored in the SQL database via the `providers`, `provider_api_keys`,
and `provider_models` tables. This module converts ORM objects into the
runtime `ProviderConfig` schema used across the gateway.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import SessionLocal
from app.logging_config import logger
from app.models import Provider, ProviderAllowedUser
from app.schemas import ProviderAPIKey, ProviderConfig
from app.services.encryption import decrypt_secret


def _convert_headers(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    headers: dict[str, str] = {}
    for key, value in raw.items():
        if key is None or value is None:
            continue
        headers[str(key)] = str(value)
    return headers or None


def _convert_retryable_codes(raw: Any) -> list[int] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        codes: list[int] = []
        for item in raw:
            try:
                codes.append(int(item))
            except (TypeError, ValueError):
                logger.warning("Skipping invalid retryable status code value: %r", item)
        return codes or None
    logger.warning("Retryable status codes payload must be a list, got %r", type(raw))
    return None


def _convert_models(provider: Provider) -> list[dict[str, Any]] | None:
    """
    Normalise ProviderModel rows (or static_models JSON) into the format
    expected by the routing layer when a provider does not expose /models.
    """
    if provider.models:
        items: list[dict[str, Any]] = []
        for entry in provider.models:
            payload: dict[str, Any] = {
                "id": entry.model_id,
                "model_id": entry.model_id,
                "family": entry.family,
                "display_name": entry.display_name,
                "context_length": entry.context_length,
                "capabilities": entry.capabilities or [],
            }
            if entry.pricing is not None:
                payload["pricing"] = entry.pricing
            if entry.metadata_json is not None:
                payload["metadata"] = entry.metadata_json
            if entry.meta_hash:
                payload["meta_hash"] = entry.meta_hash
            items.append(payload)
        return items

    if isinstance(provider.static_models, list):
        return list(provider.static_models)
    return None


def _build_api_keys(provider: Provider) -> list[ProviderAPIKey]:
    keys: list[ProviderAPIKey] = []
    for entry in provider.api_keys:
        if entry.status and entry.status.lower() != "active":
            continue
        try:
            plaintext = decrypt_secret(entry.encrypted_key)
        except ValueError:
            logger.warning(
                "Provider %s: failed to decrypt API key %s, skipping",
                provider.provider_id,
                entry.id,
            )
            continue

        keys.append(
            ProviderAPIKey(
                key=plaintext,
                weight=entry.weight or 1.0,
                max_qps=entry.max_qps,
                label=entry.label,
            )
        )
    return keys


def _normalise_transport(value: str | None) -> str:
    if not value:
        return "http"
    normalized = value.lower()
    if normalized not in {"http", "sdk"}:
        logger.warning("Provider transport %r is invalid, defaulting to http", value)
        return "http"
    return normalized


def _normalise_provider_type(value: str | None) -> str:
    if not value:
        return "native"
    normalized = value.lower()
    if normalized not in {"native", "aggregator"}:
        logger.warning("Provider type %r is invalid, defaulting to native", value)
        return "native"
    return normalized


def _build_provider_config(provider: Provider) -> ProviderConfig | None:
    api_keys = _build_api_keys(provider)
    if not api_keys:
        logger.warning(
            "Provider %s skipped because it has no active API keys",
            provider.provider_id,
        )
        return None

    data: dict[str, Any] = {
        "id": provider.provider_id,
        "name": provider.name,
        "base_url": provider.base_url,
        "transport": _normalise_transport(provider.transport),
        "provider_type": _normalise_provider_type(getattr(provider, "provider_type", None)),
        "models_path": provider.models_path or "/v1/models",
        "weight": provider.weight or 1.0,
        "api_keys": api_keys,
    }
    data["api_key"] = api_keys[0].key

    if provider.messages_path:
        trimmed = provider.messages_path.strip()
        data["messages_path"] = trimmed if trimmed else None
    chat_path = getattr(provider, "chat_completions_path", None)
    if chat_path:
        trimmed = chat_path.strip()
        data["chat_completions_path"] = trimmed if trimmed else "/v1/chat/completions"
    else:
        data["chat_completions_path"] = "/v1/chat/completions"
    responses_path = getattr(provider, "responses_path", None)
    if responses_path:
        trimmed = responses_path.strip()
        data["responses_path"] = trimmed if trimmed else None
    if provider.region:
        data["region"] = provider.region
    if provider.cost_input is not None:
        data["cost_input"] = provider.cost_input
    if provider.cost_output is not None:
        data["cost_output"] = provider.cost_output
    if provider.max_qps is not None:
        data["max_qps"] = provider.max_qps
    sdk_vendor = getattr(provider, "sdk_vendor", None)
    if sdk_vendor:
        data["sdk_vendor"] = sdk_vendor
    supported_styles = getattr(provider, "supported_api_styles", None)
    if isinstance(supported_styles, list):
        normalized = []
        for item in supported_styles:
            value = str(item or "").strip().lower()
            if value and value not in normalized:
                normalized.append(value)
        if normalized:
            data["supported_api_styles"] = normalized

    headers = _convert_headers(provider.custom_headers)
    if headers is not None:
        data["custom_headers"] = headers

    retryable = _convert_retryable_codes(provider.retryable_status_codes)
    if retryable is not None:
        data["retryable_status_codes"] = retryable

    static_models = _convert_models(provider)
    if static_models is not None:
        data["static_models"] = static_models

    try:
        return ProviderConfig(**data)
    except ValidationError as exc:
        logger.error(
            "Provider %s configuration failed validation: %s",
            provider.provider_id,
            exc,
        )
        return None


def _load_providers_from_db(
    session: Session,
    user_id: UUID | None = None,
    is_superuser: bool = False,
) -> list[Provider]:
    stmt = (
        select(Provider)
        .options(
            selectinload(Provider.api_keys),
            selectinload(Provider.models),
        )
        .order_by(Provider.provider_id)
    )
    if user_id is not None and not is_superuser:
        shared_exists = (
            select(ProviderAllowedUser.id)
            .where(
                ProviderAllowedUser.provider_uuid == Provider.id,
                ProviderAllowedUser.user_id == user_id,
            )
            .exists()
        )
        stmt = stmt.where(
            or_(
                and_(Provider.visibility == "public", Provider.owner_id.is_(None)),
                Provider.owner_id == user_id,
                and_(Provider.visibility == "restricted", shared_exists),
            )
        )
    result = session.execute(stmt)
    return list(result.scalars().all())


def load_provider_configs(
    session: Session | None = None,
    *,
    user_id: UUID | None = None,
    is_superuser: bool = False,
) -> list[ProviderConfig]:
    """
    Load providers from the database and convert them to ProviderConfig objects.

    当传入 user_id 且非超级管理员时，仅返回该用户可访问的 Provider：
    - 全局公共 Provider（visibility=public 且无 owner）
    - 用户自己创建的 Provider
    - 通过私有分享授权给该用户的 Provider（visibility=restricted）
    """
    owns_session = False
    if session is None:
        session = SessionLocal()
        owns_session = True
    try:
        providers = _load_providers_from_db(
            session,
            user_id=user_id,
            is_superuser=is_superuser,
        )
        configs: list[ProviderConfig] = []
        for provider in providers:
            cfg = _build_provider_config(provider)
            if cfg is not None:
                configs.append(cfg)
        return configs
    finally:
        if owns_session:
            session.close()


def load_providers_with_configs(
    session: Session | None = None,
    *,
    user_id: UUID | None = None,
    is_superuser: bool = False,
) -> list[tuple[Provider, ProviderConfig]]:
    """
    Load providers and keep their ORM objects for downstream persistence needs.

    This is similar to ``load_provider_configs`` but returns tuples so that
    callers can both perform health checks (using ProviderConfig) and update
    runtime status on the ORM instance.
    """

    owns_session = False
    if session is None:
        session = SessionLocal()
        owns_session = True
    try:
        providers = _load_providers_from_db(
            session,
            user_id=user_id,
            is_superuser=is_superuser,
        )
        pairs: list[tuple[Provider, ProviderConfig]] = []
        for provider in providers:
            cfg = _build_provider_config(provider)
            if cfg is None:
                continue
            pairs.append((provider, cfg))
        return pairs
    finally:
        if owns_session:
            session.close()


def get_provider_config(provider_id: str, session: Session | None = None) -> ProviderConfig | None:
    """
    Load a single provider configuration by its slug/identifier.
    """
    owns_session = False
    if session is None:
        session = SessionLocal()
        owns_session = True
    try:
        stmt = (
            select(Provider)
            .where(Provider.provider_id == provider_id)
            .options(
                selectinload(Provider.api_keys),
                selectinload(Provider.models),
            )
        )
        result = session.execute(stmt).scalars().first()
        if result is None:
            return None
        return _build_provider_config(result)
    finally:
        if owns_session:
            session.close()


__all__ = ["get_provider_config", "load_provider_configs", "load_providers_with_configs"]
