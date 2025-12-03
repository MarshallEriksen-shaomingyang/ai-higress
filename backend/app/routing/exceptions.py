from __future__ import annotations

from collections.abc import Sequence


class NoAllowedProvidersAvailable(RuntimeError):
    """Raised when an API key has no overlap with candidate providers."""

    def __init__(self, api_key_id: str, allowed_provider_ids: Sequence[str]):
        self.api_key_id = api_key_id
        self.allowed_provider_ids = list(allowed_provider_ids)
        message = "API key has no allowed providers among the candidates"
        super().__init__(message)


__all__ = ["NoAllowedProvidersAvailable"]
