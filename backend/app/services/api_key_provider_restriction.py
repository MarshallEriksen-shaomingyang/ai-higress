from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models import APIKey
from app.repositories.api_key_provider_restriction_repository import (
    APIKeyProviderRestrictionError,
    UnknownProviderError,
    clear_all_restrictions,
    is_provider_allowed,
    list_allowed_provider_ids,
    replace_allowed_providers,
)


class APIKeyProviderRestrictionService:
    """Manage the provider allow-list attached to an API key."""

    def __init__(self, session: Session):
        self.session = session

    def set_allowed_providers(
        self,
        api_key: APIKey,
        provider_ids: Sequence[str],
    ) -> list[str]:
        return replace_allowed_providers(self.session, api_key=api_key, provider_ids=provider_ids)

    def get_allowed_provider_ids(self, api_key: APIKey) -> list[str]:
        return list_allowed_provider_ids(self.session, api_key_id=api_key.id)

    def is_provider_allowed(self, api_key: APIKey, provider_id: str) -> bool:
        return is_provider_allowed(self.session, api_key=api_key, provider_id=provider_id)

    def clear_all_restrictions(self, api_key: APIKey) -> None:
        clear_all_restrictions(self.session, api_key=api_key)


__all__ = [
    "APIKeyProviderRestrictionError",
    "APIKeyProviderRestrictionService",
    "UnknownProviderError",
]
