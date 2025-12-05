
import os
from pathlib import Path

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
    # Calculate the project root directory (two levels up from this file)
    _project_root = Path(__file__).parent.parent.parent
    
    model_config = SettingsConfigDict(
        env_file=str(_project_root / ".env"),
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

    # Celery task queue configuration (defaults assume local Redis; override in .env for Docker/prod).
    celery_broker_url: str = Field(
        "redis://localhost:6379/0",
        alias="CELERY_BROKER_URL",
        description="Celery broker URL; typically a Redis instance, e.g. redis://:password@redis:6379/1",
    )
    celery_result_backend: str = Field(
        "redis://localhost:6379/0",
        alias="CELERY_RESULT_BACKEND",
        description="Celery result backend URL; can reuse the broker URL or a dedicated DB.",
    )
    celery_task_default_queue: str = Field(
        "default",
        alias="CELERY_TASK_DEFAULT_QUEUE",
        description="Default Celery queue name.",
    )
    celery_timezone: str = Field(
        "Asia/Shanghai",
        alias="CELERY_TIMEZONE",
        description="Timezone used by Celery beat / scheduled tasks.",
    )

    # Provider health-check intervals and cache TTL
    provider_health_check_interval_seconds: int = Field(
        60,
        alias="PROVIDER_HEALTH_CHECK_INTERVAL_SECONDS",
        description="定时检测厂商健康状态的间隔（秒）",
        ge=10,
    )
    provider_health_cache_ttl_seconds: int = Field(
        300,
        alias="PROVIDER_HEALTH_CACHE_TTL_SECONDS",
        description="厂商健康状态写入 Redis 时的缓存 TTL（秒）",
        ge=30,
    )

    # API Key 健康巡检与异常禁用
    api_key_health_check_interval_seconds: int = Field(
        300,
        alias="API_KEY_HEALTH_CHECK_INTERVAL_SECONDS",
        description="定期扫描过期 API Key 的时间间隔（秒）",
        ge=60,
    )
    api_key_error_scan_interval_seconds: int = Field(
        600,
        alias="API_KEY_ERROR_SCAN_INTERVAL_SECONDS",
        description="定期扫描高错误率 API Key 的时间间隔（秒）",
        ge=60,
    )
    api_key_error_window_minutes: int = Field(
        15,
        alias="API_KEY_ERROR_WINDOW_MINUTES",
        description="计算错误率时向前回溯的时间窗口（分钟）",
        ge=1,
    )
    api_key_error_rate_threshold: float = Field(
        0.6,
        alias="API_KEY_ERROR_RATE_THRESHOLD",
        description="超过该错误率的 API Key 将被自动禁用",
        ge=0.0,
        le=1.0,
    )
    api_key_error_min_requests: int = Field(
        20,
        alias="API_KEY_ERROR_MIN_REQUESTS",
        description="仅当时间窗内请求量达到该阈值时才触发禁用逻辑",
        ge=1,
    )

    # Metrics buffer & sampling
    metrics_buffer_enabled: bool = Field(
        True,
        alias="METRICS_BUFFER_ENABLED",
        description="是否启用本地指标缓冲，按批写入数据库",
    )
    metrics_flush_interval_seconds: int = Field(
        30,
        alias="METRICS_FLUSH_INTERVAL_SECONDS",
        description="指标缓冲刷新间隔（秒）",
        ge=1,
    )
    metrics_latency_sample_size: int = Field(
        128,
        alias="METRICS_LATENCY_SAMPLE_SIZE",
        description="每个时间桶保留的延迟样本量，用于估算分位数",
        ge=0,
    )
    metrics_max_buffered_buckets: int = Field(
        500,
        alias="METRICS_MAX_BUFFERED_BUCKETS",
        description="触发异步刷新前允许积累的最大桶数",
        ge=1,
    )
    metrics_success_sample_rate: float = Field(
        1.0,
        alias="METRICS_SUCCESS_SAMPLE_RATE",
        description="成功请求的采样率（0~1）；失败请求始终全量记录",
        ge=0.0,
        le=1.0,
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

    # Per-user private provider limits and shared-provider approval behaviour.
    default_user_private_provider_limit: int = Field(
        3,
        alias="DEFAULT_USER_PRIVATE_PROVIDER_LIMIT",
        description="默认每个用户可创建的私有提供商数量上限",
        ge=0,
    )
    max_user_private_provider_limit: int = Field(
        20,
        alias="MAX_USER_PRIVATE_PROVIDER_LIMIT",
        description="系统允许设置的最大私有提供商上限（用于管理员面板校验）",
        ge=0,
    )
    require_approval_for_shared_providers: bool = Field(
        True,
        alias="REQUIRE_APPROVAL_FOR_SHARED_PROVIDERS",
        description="是否要求用户提交的共享提供商必须经过管理员审核",
    )

    # Credit / billing settings
    credits_base_per_1k_tokens: int = Field(
        10,
        alias="CREDITS_BASE_PER_1K_TOKENS",
        description="基础计费单价：1x 模型每 1000 tokens 消耗的积分数",
        ge=0,
    )
    initial_user_credits: int = Field(
        0,
        alias="INITIAL_USER_CREDITS",
        description="新建用户默认初始化的积分余额",
        ge=0,
    )
    enable_credit_check: bool = Field(
        False,
        alias="ENABLE_CREDIT_CHECK",
        description="是否在网关层强制校验用户积分余额，不足时拒绝请求",
    )
    streaming_min_tokens: int = Field(
        500,
        alias="STREAMING_MIN_TOKENS",
        description="流式请求在无法获取 usage 时用于预估扣费的最小 token 数",
        ge=0,
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
