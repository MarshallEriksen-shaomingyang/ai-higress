from typing import Dict, List, Optional

from pydantic import Field

try:
    # Prefer real pydantic-settings when available.
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    class BaseSettings:  # type: ignore[misc]
        """
        Minimal stand-in for pydantic_settings.BaseSettings used when the
        dependency is not installed (e.g., in constrained test environments).

        It behaves like a simple object with attribute defaults.
        """

        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)

    class SettingsConfigDict(dict):  # type: ignore[misc]
        pass


class Settings(BaseSettings):
    # Read from OS env and optional .env file in project root.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis connection string
    redis_url: str = Field(
        "redis://localhost:6379/0",
        alias="REDIS_URL",
        description="Redis connection URL, e.g. 'redis://redis:6379/0'",
    )

    # HTTP timeouts
    upstream_timeout: float = 600.0

    # Models cache TTL in seconds
    models_cache_ttl: int = Field(300, alias="MODELS_CACHE_TTL")

    # Browser-mimic headers for upstream (掩护功能)
    mask_as_browser: bool = Field(True, alias="MASK_AS_BROWSER")
    mask_user_agent: str = Field(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        alias="MASK_USER_AGENT",
    )
    mask_origin: Optional[str] = Field(None, alias="MASK_ORIGIN")
    mask_referer: Optional[str] = Field(None, alias="MASK_REFERER")

    # Multi-provider configuration (001-model-routing).
    # Raw provider id list; concrete provider configs are derived from this.
    llm_providers_raw: Optional[str] = Field(
        default=None,
        alias="LLM_PROVIDERS",
        description="Comma-separated provider ids, e.g. 'openai,azure,local'",
    )

    # Application log level for our apiproxy logger.
    # Can be overridden via LOG_LEVEL env var, e.g. "DEBUG" while debugging.
    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Application log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    # Shared API token required by clients when calling this gateway.
    api_auth_token: str = Field(
        "timeline",
        alias="APIPROXY_AUTH_TOKEN",
        description="Expected token after base64 decoding the Authorization header",
    )

    def get_llm_provider_ids(self) -> List[str]:
        """
        Return configured provider ids from LLM_PROVIDERS.
        Whitespace is stripped and empty entries are ignored.
        """
        if not self.llm_providers_raw:
            return []
        return [
            item.strip()
            for item in self.llm_providers_raw.split(",")
            if item.strip()
        ]


settings = Settings()  # Reads from environment if available


def build_upstream_headers() -> Dict[str, str]:
    """
    Build headers for calling upstream, optionally mimicking a browser page.

    This is a generic helper used in places where we do not have a
    ProviderConfig instance (e.g. some legacy utilities). The
    multi-provider routing layer constructs provider-specific headers
    separately based on ProviderConfig.
    """
    headers: Dict[str, str] = {
        "Accept": "application/json",
    }

    if settings.mask_as_browser:
        headers["User-Agent"] = settings.mask_user_agent
        if settings.mask_origin:
            headers["Origin"] = settings.mask_origin
        if settings.mask_referer:
            headers["Referer"] = settings.mask_referer

    return headers
