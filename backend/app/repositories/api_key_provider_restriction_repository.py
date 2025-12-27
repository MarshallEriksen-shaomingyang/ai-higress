from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import APIKey, APIKeyAllowedProvider, Provider


class APIKeyProviderRestrictionError(RuntimeError):
    """API Key 的 provider allow-list 相关错误。"""


class UnknownProviderError(APIKeyProviderRestrictionError):
    def __init__(self, missing_ids: set[str]):
        self.missing_ids = missing_ids
        message = "Unknown provider ids: " + ", ".join(sorted(missing_ids))
        super().__init__(message)


def list_allowed_provider_ids(db: Session, *, api_key_id: object) -> list[str]:
    stmt = select(APIKeyAllowedProvider.provider_id).where(
        APIKeyAllowedProvider.api_key_id == api_key_id
    )
    return list(db.execute(stmt).scalars().all())


def is_provider_allowed(
    db: Session,
    *,
    api_key: APIKey,
    provider_id: str,
) -> bool:
    if not api_key.has_provider_restrictions:
        return True
    stmt = select(APIKeyAllowedProvider.provider_id).where(
        APIKeyAllowedProvider.api_key_id == api_key.id,
        APIKeyAllowedProvider.provider_id == provider_id,
    )
    return db.execute(stmt).first() is not None


def clear_all_restrictions(db: Session, *, api_key: APIKey) -> None:
    stmt = delete(APIKeyAllowedProvider).where(
        APIKeyAllowedProvider.api_key_id == api_key.id
    )
    db.execute(stmt)
    api_key.has_provider_restrictions = False
    db.flush()
    db.expire(api_key, ["allowed_provider_links"])


def replace_allowed_providers(
    db: Session,
    *,
    api_key: APIKey,
    provider_ids: Sequence[str],
) -> list[str]:
    normalized = _normalize_ids(provider_ids)
    if not normalized:
        clear_all_restrictions(db, api_key=api_key)
        return []

    _ensure_all_providers_exist(db, provider_ids=normalized)
    current = set(list_allowed_provider_ids(db, api_key_id=api_key.id))
    desired = set(normalized)

    to_remove = current - desired
    to_add = desired - current

    if to_remove:
        stmt = delete(APIKeyAllowedProvider).where(
            APIKeyAllowedProvider.api_key_id == api_key.id,
            APIKeyAllowedProvider.provider_id.in_(to_remove),
        )
        db.execute(stmt)

    for pid in to_add:
        db.add(APIKeyAllowedProvider(api_key_id=api_key.id, provider_id=pid))

    api_key.has_provider_restrictions = True
    db.flush()
    db.expire(api_key, ["allowed_provider_links"])
    return sorted(desired)


def _normalize_ids(provider_ids: Sequence[str]) -> list[str]:
    cleaned: set[str] = set()
    for provider_id in provider_ids:
        trimmed = (provider_id or "").strip()
        if trimmed:
            cleaned.add(trimmed)
    return sorted(cleaned)


def _ensure_all_providers_exist(db: Session, *, provider_ids: Sequence[str]) -> None:
    if not provider_ids:
        return
    stmt = select(Provider.provider_id).where(Provider.provider_id.in_(provider_ids))
    found = set(db.execute(stmt).scalars().all())
    missing = set(provider_ids) - found
    if missing:
        raise UnknownProviderError(missing)


__all__ = [
    "APIKeyProviderRestrictionError",
    "UnknownProviderError",
    "clear_all_restrictions",
    "is_provider_allowed",
    "list_allowed_provider_ids",
    "replace_allowed_providers",
]

