
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
    database_url: str = Field(
        "postgresql+psycopg://postgres:postgres@localhost:5432/apiproxy",
        alias="DATABASE_URL",
        description="SQLAlchemy database URL, e.g. postgresql+psycopg://user:pass@host:port/db",
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
    mask_origin: str | None = Field(None, alias="MASK_ORIGIN")
    mask_referer: str | None = Field(None, alias="MASK_REFERER")

    # Application log level for our apiproxy logger.
    # Can be overridden via LOG_LEVEL env var, e.g. "DEBUG" while debugging.
    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Application log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    log_timezone: str | None = Field(
        default=None,
        alias="LOG_TIMEZONE",
        description="Timezone name for log timestamps, e.g. 'Asia/Shanghai'. Defaults to system local time.",
    )

    # Secret key for hashing/encrypting sensitive data (e.g. key preference hash).
    secret_key: str = Field(
        "please-change-me",
        alias="SECRET_KEY",
        description="Secret key used to derive hashed identifiers for API keys; please override in production",
    )

settings = Settings()  # Reads from environment if available


def build_upstream_headers() -> dict[str, str]:
    """
    Build headers for calling upstream, optionally mimicking a browser page.

    This is a generic helper used in places where we do not have a
    ProviderConfig instance (e.g. some legacy utilities). The
    multi-provider routing layer constructs provider-specific headers
    separately based on ProviderConfig.
    """
    headers: dict[str, str] = {
        "Accept": "application/json",
    }

    if settings.mask_as_browser:
        headers["User-Agent"] = settings.mask_user_agent
        if settings.mask_origin:
            headers["Origin"] = settings.mask_origin
        if settings.mask_referer:
            headers["Referer"] = settings.mask_referer

    return headers
