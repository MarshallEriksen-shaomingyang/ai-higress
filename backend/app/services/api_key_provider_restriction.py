from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import APIKey, APIKeyAllowedProvider, Provider


class APIKeyProviderRestrictionError(RuntimeError):
    """Base error for provider restriction operations."""


class UnknownProviderError(APIKeyProviderRestrictionError):
    def __init__(self, missing_ids: set[str]):
        self.missing_ids = missing_ids
        message = "Unknown provider ids: " + ", ".join(sorted(missing_ids))
        super().__init__(message)


class APIKeyProviderRestrictionService:
    """Manage the provider allow-list attached to an API key."""

    def __init__(self, session: Session):
        self.session = session

    def set_allowed_providers(
        self,
        api_key: APIKey,
        provider_ids: Sequence[str],
    ) -> list[str]:
        normalized = self._normalize_ids(provider_ids)
        if not normalized:
            self.clear_all_restrictions(api_key)
            return []

        self._ensure_all_providers_exist(normalized)
        current = set(self.get_allowed_provider_ids(api_key))
        desired = set(normalized)

        to_remove = current - desired
        to_add = desired - current

        if to_remove:
            stmt = delete(APIKeyAllowedProvider).where(
                APIKeyAllowedProvider.api_key_id == api_key.id,
                APIKeyAllowedProvider.provider_id.in_(to_remove),
            )
            self.session.execute(stmt)

        for provider_id in to_add:
            self.session.add(
                APIKeyAllowedProvider(api_key_id=api_key.id, provider_id=provider_id)
            )

        api_key.has_provider_restrictions = True
        self.session.flush()
        self.session.expire(api_key, ["allowed_provider_links"])
        return sorted(desired)

    def get_allowed_provider_ids(self, api_key: APIKey) -> list[str]:
        stmt = select(APIKeyAllowedProvider.provider_id).where(
            APIKeyAllowedProvider.api_key_id == api_key.id
        )
        rows = self.session.execute(stmt).scalars().all()
        return list(rows)

    def is_provider_allowed(self, api_key: APIKey, provider_id: str) -> bool:
        if not api_key.has_provider_restrictions:
            return True
        stmt = select(APIKeyAllowedProvider.provider_id).where(
            APIKeyAllowedProvider.api_key_id == api_key.id,
            APIKeyAllowedProvider.provider_id == provider_id,
        )
        return self.session.execute(stmt).first() is not None

    def clear_all_restrictions(self, api_key: APIKey) -> None:
        stmt = delete(APIKeyAllowedProvider).where(
            APIKeyAllowedProvider.api_key_id == api_key.id
        )
        self.session.execute(stmt)
        api_key.has_provider_restrictions = False
        self.session.flush()
        self.session.expire(api_key, ["allowed_provider_links"])

    def _normalize_ids(self, provider_ids: Sequence[str]) -> list[str]:
        cleaned: set[str] = set()
        for provider_id in provider_ids:
            trimmed = (provider_id or "").strip()
            if trimmed:
                cleaned.add(trimmed)
        return sorted(cleaned)

    def _ensure_all_providers_exist(self, provider_ids: Sequence[str]) -> None:
        if not provider_ids:
            return
        stmt = select(Provider.provider_id).where(Provider.provider_id.in_(provider_ids))
        found = set(self.session.execute(stmt).scalars().all())
        missing = set(provider_ids) - found
        if missing:
            raise UnknownProviderError(missing)


__all__ = [
    "APIKeyProviderRestrictionError",
    "APIKeyProviderRestrictionService",
    "UnknownProviderError",
]
