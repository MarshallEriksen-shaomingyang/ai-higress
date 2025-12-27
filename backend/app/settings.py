
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

# 只在实际运行时导入，类型检查时跳过
if not TYPE_CHECKING:
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

            def __init__(self, **data: Any) -> None:
                for k, v in data.items():
                    setattr(self, k, v)

        class SettingsConfigDict(dict):  # type: ignore[misc]
            pass
else:
    # 类型检查时使用的简化版本
    class BaseSettings:  # type: ignore[no-redef]
        pass

    class SettingsConfigDict(dict):  # type: ignore[no-redef]
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

    # CORS 配置
    cors_allow_origins: str = Field(
        "http://localhost:3000",
        alias="CORS_ALLOW_ORIGINS",
        description="允许的跨域来源，多个来源用逗号分隔"
    )

    cors_allow_credentials: bool = Field(
        True,
        alias="CORS_ALLOW_CREDENTIALS",
        description="是否允许跨域请求携带凭证"
    )

    cors_allow_methods: str = Field(
        "*",
        alias="CORS_ALLOW_METHODS",
        description="允许的跨域请求方法，多个方法用逗号分隔，* 表示所有方法"
    )

    cors_allow_headers: str = Field(
        "*",
        alias="CORS_ALLOW_HEADERS",
        description="允许的跨域请求头，多个头用逗号分隔，* 表示所有头"
    )

    # Environment / mode
    environment: str = Field(
        "development",
        alias="APP_ENV",
        description="当前运行环境，例如 development / production；默认 development",
    )
    security_middleware_override: bool | None = Field(
        default=None,
        alias="ENABLE_SECURITY_MIDDLEWARE",
        description="显式控制是否启用安全中间件栈：true 强制开启，false 强制关闭；默认根据 APP_ENV=production 判断",
    )
    api_docs_override: bool | None = Field(
        default=None,
        alias="ENABLE_API_DOCS",
        description=(
            "显式控制是否启用 FastAPI 文档路由（/docs、/redoc、/openapi.json）："
            "true 强制开启，false 强制关闭；默认在 APP_ENV=production 时关闭"
        ),
    )
    # 初始管理员
    default_admin_username: str = Field(
        "admin",
        alias="DEFAULT_ADMIN_USERNAME",
        description="首次启动时初始化的默认管理员用户名",
    )
    default_admin_email: str = Field(
        "admin@example.com",
        alias="DEFAULT_ADMIN_EMAIL",
        description="首次启动时初始化的默认管理员邮箱",
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
    auto_apply_db_migrations: bool = Field(
        True,
        alias="AUTO_APPLY_DB_MIGRATIONS",
        description="进程启动时自动执行 Alembic 升级，确保 schema 与代码一致。",
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

    # Provider probe/audit intervals and cache TTL
    provider_audit_auto_probe_interval_seconds: int = Field(
        1800,
        alias="PROVIDER_AUDIT_AUTO_PROBE_INTERVAL_SECONDS",
        description="待审核 Provider 自动探针间隔（秒）",
        ge=60,
    )
    provider_audit_cron_interval_seconds: int = Field(
        3600,
        alias="PROVIDER_AUDIT_CRON_INTERVAL_SECONDS",
        description="上线 Provider 巡检间隔（秒）",
        ge=120,
    )
    provider_health_cache_ttl_seconds: int = Field(
        300,
        alias="PROVIDER_HEALTH_CACHE_TTL_SECONDS",
        description="厂商健康状态写入 Redis 时的缓存 TTL（秒）",
        ge=30,
    )

    # Upstream proxy pool (DB/Redis managed) - scheduler knobs
    upstream_proxy_refresh_scheduler_interval_seconds: int = Field(
        60,
        alias="UPSTREAM_PROXY_REFRESH_SCHEDULER_INTERVAL_SECONDS",
        description="Celery beat 触发远程代理列表刷新的调度间隔（秒）",
        ge=10,
    )
    upstream_proxy_healthcheck_scheduler_interval_seconds: int = Field(
        60,
        alias="UPSTREAM_PROXY_HEALTHCHECK_SCHEDULER_INTERVAL_SECONDS",
        description="Celery beat 触发代理测活的调度间隔（秒）",
        ge=10,
    )
    upstream_proxy_default_refresh_interval_seconds: int = Field(
        300,
        alias="UPSTREAM_PROXY_DEFAULT_REFRESH_INTERVAL_SECONDS",
        description="当代理来源未配置 refresh_interval_seconds 时使用的默认刷新间隔（秒）",
        ge=30,
    )
    upstream_proxy_healthcheck_concurrency: int = Field(
        20,
        alias="UPSTREAM_PROXY_HEALTHCHECK_CONCURRENCY",
        description="代理测活并发数（避免一次性创建过多连接）",
        ge=1,
    )
    probe_prompt: str = Field(
        "请回答一个简单问题用于健康检查。",
        alias="PROBE_PROMPT",
        description="预留字段：将来用于 health 全局扩展的探针提示词（当前版本不生效，保留给后续实现）",
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

    # Provider health check and routing
    enable_provider_health_check: bool = Field(
        True,
        alias="ENABLE_PROVIDER_HEALTH_CHECK",
        description="是否启用 Provider 健康状态检查和路由过滤（关闭后将忽略 Provider 状态和最低分数过滤）",
    )

    # Provider 实时故障标记（用于快速跳过故障 Provider）
    provider_failure_cooldown_seconds: int = Field(
        60,
        alias="PROVIDER_FAILURE_COOLDOWN_SECONDS",
        description="Provider 故障冷却期（秒）；在此期间内失败次数超过阈值的 Provider 将被跳过",
        ge=10,
        le=600,
    )
    provider_failure_threshold: int = Field(
        3,
        alias="PROVIDER_FAILURE_THRESHOLD",
        description="Provider 故障阈值；在冷却期内失败次数超过此值将被跳过",
        ge=1,
        le=10,
    )

    candidate_availability_cache_ttl_seconds: int = Field(
        10,
        alias="CANDIDATE_AVAILABILITY_CACHE_TTL_SECONDS",
        description="ProviderSelector.check_candidate_availability 结果缓存 TTL（秒）；0 表示关闭",
        ge=0,
        le=300,
    )

    enable_bandit_routing_weight: bool = Field(
        False,
        alias="ENABLE_BANDIT_ROUTING_WEIGHT",
        description="是否启用 contextual bandit 对路由动态权重的策略映射（按项目/助手/上下文隔离）",
    )
    bandit_routing_top_n: int = Field(
        2,
        alias="BANDIT_ROUTING_TOP_N",
        description="bandit 策略提升的 TopN provider 数量",
        ge=1,
        le=10,
    )
    bandit_routing_max_boost: float = Field(
        0.3,
        alias="BANDIT_ROUTING_MAX_BOOST",
        description="Top1 provider 的最大加权比例（例如 0.3 表示 *1.3）",
        ge=0.0,
        le=2.0,
    )
    bandit_routing_rank_decay: float = Field(
        0.6,
        alias="BANDIT_ROUTING_RANK_DECAY",
        description="TopN 加权衰减系数（Top2=Top1*decay，Top3=Top1*decay^2）",
        ge=0.0,
        le=1.0,
    )
    bandit_routing_min_samples_per_arm: int = Field(
        10,
        alias="BANDIT_ROUTING_MIN_SAMPLES_PER_ARM",
        description="bandit 样本不足时不应用策略（仅在 exploration 且 apply_during_exploration=false 时生效）",
        ge=0,
        le=1000,
    )
    bandit_routing_apply_during_exploration: bool = Field(
        False,
        alias="BANDIT_ROUTING_APPLY_DURING_EXPLORATION",
        description="是否在 exploration 阶段也应用 bandit 路由加权（默认关闭，避免冷启动随机扰动）",
    )

    # User probe tasks (user-managed chat probes)
    user_probe_scheduler_interval_seconds: int = Field(
        60,
        alias="USER_PROBE_SCHEDULER_INTERVAL_SECONDS",
        description="用户探针任务调度间隔（秒）；调度器将扫描到期任务并触发一次真实对话请求",
        ge=10,
    )
    user_probe_timeout_seconds: float = Field(
        15.0,
        alias="USER_PROBE_TIMEOUT_SECONDS",
        description="用户探针对话请求超时时间（秒）",
        gt=0.5,
    )
    user_probe_min_interval_seconds: int = Field(
        300,
        alias="USER_PROBE_MIN_INTERVAL_SECONDS",
        description="用户探针任务最小执行间隔（秒），用于限制过高频率造成成本/压力",
        ge=60,
    )
    user_probe_max_interval_seconds: int = Field(
        86400,
        alias="USER_PROBE_MAX_INTERVAL_SECONDS",
        description="用户探针任务最大执行间隔（秒）",
        ge=60,
    )
    user_probe_max_tasks_per_user: int = Field(
        10,
        alias="USER_PROBE_MAX_TASKS_PER_USER",
        description="单用户允许创建的最大探针任务数量",
        ge=0,
    )
    user_probe_max_runs_per_task: int = Field(
        50,
        alias="USER_PROBE_MAX_RUNS_PER_TASK",
        description="单个探针任务保留的最大历史执行记录数（超出将清理最旧记录）",
        ge=1,
    )
    user_probe_max_due_tasks_per_tick: int = Field(
        50,
        alias="USER_PROBE_MAX_DUE_TASKS_PER_TICK",
        description="每次调度 tick 最多处理的到期探针任务数，避免单次任务耗时过长",
        ge=1,
    )
    user_probe_max_prompt_length: int = Field(
        2000,
        alias="USER_PROBE_MAX_PROMPT_LENGTH",
        description="探针提示词最大长度（字符）",
        ge=1,
    )
    user_probe_default_max_tokens: int = Field(
        16,
        alias="USER_PROBE_DEFAULT_MAX_TOKENS",
        description="新建探针任务默认 max_tokens",
        ge=1,
    )
    user_probe_max_tokens_limit: int = Field(
        256,
        alias="USER_PROBE_MAX_TOKENS_LIMIT",
        description="探针任务 max_tokens 上限（避免误配置导致成本过高）",
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

    # Offline metrics recomputation
    offline_metrics_enabled: bool = Field(
        True,
        alias="OFFLINE_METRICS_ENABLED",
        description="是否启用离线指标重算定时任务；关闭时仅保留手动重算入口",
    )
    offline_metrics_windows: list[int] = Field(
        default_factory=lambda: [300, 3600],
        alias="OFFLINE_METRICS_WINDOWS",
        description="离线重算落库的时间窗口（秒），如 300=5 分钟，3600=1 小时",
    )
    offline_metrics_diff_threshold: float = Field(
        0.05,
        alias="OFFLINE_METRICS_DIFF_THRESHOLD",
        description="分位数/错误率相对变化超过该阈值才触发写回",
        ge=0.0,
    )
    offline_metrics_lookback_hours: int = Field(
        6,
        alias="OFFLINE_METRICS_LOOKBACK_HOURS",
        description="定时任务默认回溯的小时数",
        ge=1,
    )
    offline_metrics_guard_hours: int = Field(
        0,
        alias="OFFLINE_METRICS_GUARD_HOURS",
        description="重算窗口向历史偏移的保护小时数，例如 2 表示不覆盖最近 2 小时",
        ge=0,
    )
    offline_metrics_interval_seconds: int = Field(
        900,
        alias="OFFLINE_METRICS_INTERVAL_SECONDS",
        description="离线重算定时任务的触发间隔（秒）",
        ge=60,
    )
    offline_metrics_source_version: str = Field(
        "offline-recalc-v1",
        alias="OFFLINE_METRICS_SOURCE_VERSION",
        description="aggregate_metrics 写回的版本标识",
    )
    offline_metrics_min_total_requests: int = Field(
        1,
        alias="OFFLINE_METRICS_MIN_TOTAL_REQUESTS",
        description="参与离线聚合的最小请求数阈值",
        ge=0,
    )

    # User session & JWT 管理
    max_sessions_per_user: int = Field(
        5,
        alias="MAX_SESSIONS_PER_USER",
        description="单个用户允许的最大活跃会话数（超过时自动淘汰最旧会话）",
        ge=1,
    )
    user_session_cleanup_interval_seconds: int = Field(
        900,
        alias="USER_SESSION_CLEANUP_INTERVAL_SECONDS",
        description="定期清理 Redis 中用户会话索引中无效/损坏记录的时间间隔（秒）",
        ge=60,
    )

    # LinuxDo OAuth
    linuxdo_enabled: bool = Field(
        False,
        alias="LINUXDO_OAUTH_ENABLED",
        description="是否启用 LinuxDo Connect OAuth 登录",
    )
    linuxdo_client_id: str | None = Field(
        default=None,
        alias="LINUXDO_CLIENT_ID",
        description="LinuxDo Connect 应用的 Client ID",
    )
    linuxdo_client_secret: str | None = Field(
        default=None,
        alias="LINUXDO_CLIENT_SECRET",
        description="LinuxDo Connect 应用的 Client Secret",
    )
    linuxdo_redirect_uri: str | None = Field(
        default=None,
        alias="LINUXDO_REDIRECT_URI",
        description="LinuxDo OAuth 回调地址（通常为前端 /callback 页面）",
    )
    linuxdo_authorize_endpoint: str = Field(
        "https://connect.linux.do/oauth2/authorize",
        alias="LINUXDO_AUTHORIZE_ENDPOINT",
        description="LinuxDo 授权端点",
    )
    linuxdo_token_endpoint: str = Field(
        "https://connect.linux.do/oauth2/token",
        alias="LINUXDO_TOKEN_ENDPOINT",
        description="LinuxDo Token 端点",
    )
    linuxdo_userinfo_endpoint: str = Field(
        "https://connect.linux.do/api/user",
        alias="LINUXDO_USERINFO_ENDPOINT",
        description="LinuxDo 用户信息端点",
    )

    # Gateway public configuration (exposed to users on the UI)
    gateway_api_base_url: str = Field(
        "http://localhost:8000",
        alias="GATEWAY_API_BASE_URL",
        description="对外暴露给最终用户使用的网关 API 基础 URL，例如 https://api.example.com",
    )
    gateway_max_concurrent_requests: int = Field(
        1000,
        alias="GATEWAY_MAX_CONCURRENT_REQUESTS",
        description="系统推荐或配置的最大并发请求数，用于文档展示或将来的限流策略",
        ge=1,
    )
    gateway_request_timeout_ms: int = Field(
        30000,
        alias="GATEWAY_REQUEST_TIMEOUT_MS",
        description="推荐给调用方的请求超时时间（毫秒），例如 30000 表示 30 秒",
        ge=1000,
    )
    gateway_cache_ttl_seconds: int = Field(
        3600,
        alias="GATEWAY_CACHE_TTL_SECONDS",
        description="推荐的缓存 TTL（秒），用于调用方理解网关缓存行为",
        ge=0,
    )
    dashboard_metrics_retention_days: int = Field(
        15,
        alias="DASHBOARD_METRICS_RETENTION_DAYS",
        description="Dashboard 指标分钟桶历史数据保留天数（用于控制 provider_routing_metrics_history 表的留存）",
        ge=7,
        le=30,
    )
    dashboard_metrics_cleanup_enabled: bool = Field(
        True,
        alias="DASHBOARD_METRICS_CLEANUP_ENABLED",
        description="是否启用 Dashboard 指标分钟桶历史数据的定期清理任务（Celery beat）",
    )
    dashboard_metrics_cleanup_interval_seconds: int = Field(
        86400,
        alias="DASHBOARD_METRICS_CLEANUP_INTERVAL_SECONDS",
        description="Dashboard 指标清理任务的调度间隔（秒）",
        ge=60,
    )
    dashboard_metrics_cleanup_batch_size: int = Field(
        5000,
        alias="DASHBOARD_METRICS_CLEANUP_BATCH_SIZE",
        description="清理任务每批删除的最大行数（避免单次大事务造成锁与膨胀）",
        ge=100,
        le=50000,
    )
    dashboard_metrics_rollup_enabled: bool = Field(
        True,
        alias="DASHBOARD_METRICS_ROLLUP_ENABLED",
        description="是否启用 Dashboard 指标的 hour/day rollup（Celery beat）",
    )
    dashboard_metrics_rollup_guard_minutes: int = Field(
        2,
        alias="DASHBOARD_METRICS_ROLLUP_GUARD_MINUTES",
        description="rollup 统计的保护时间（分钟），避免与最新写入强竞争",
        ge=0,
        le=60,
    )
    dashboard_metrics_rollup_hourly_interval_seconds: int = Field(
        300,
        alias="DASHBOARD_METRICS_ROLLUP_HOURLY_INTERVAL_SECONDS",
        description="hourly rollup 调度间隔（秒）",
        ge=60,
    )
    dashboard_metrics_rollup_daily_interval_seconds: int = Field(
        3600,
        alias="DASHBOARD_METRICS_ROLLUP_DAILY_INTERVAL_SECONDS",
        description="daily rollup 调度间隔（秒）",
        ge=300,
    )
    dashboard_metrics_hourly_retention_days: int = Field(
        90,
        alias="DASHBOARD_METRICS_HOURLY_RETENTION_DAYS",
        description="hourly rollup 数据保留天数",
        ge=7,
    )
    dashboard_metrics_daily_retention_days: int = Field(
        365,
        alias="DASHBOARD_METRICS_DAILY_RETENTION_DAYS",
        description="daily rollup 数据保留天数",
        ge=30,
    )

    # HTTP timeouts
    upstream_timeout: float = 600.0
    upstream_proxy_max_retries: int = Field(
        1,
        alias="UPSTREAM_PROXY_MAX_RETRIES",
        description="同一次上游请求内，代理连接失败时的最大换代理重试次数；0 表示不重试。",
        ge=0,
    )

    # Models cache TTL in seconds
    models_cache_ttl: int = Field(300, alias="MODELS_CACHE_TTL")

    # Bridge / MCP tunnel gateway (internal)
    bridge_gateway_url: str = Field(
        "http://127.0.0.1:8088",
        alias="BRIDGE_GATEWAY_URL",
        description="Tunnel Gateway internal base URL (Backend -> Gateway)",
    )
    bridge_gateway_internal_token: str = Field(
        "",
        alias="BRIDGE_GATEWAY_INTERNAL_TOKEN",
        description="Shared token for Tunnel Gateway internal APIs (X-Internal-Token)",
    )
    bridge_gateway_events_path: str = Field(
        "/internal/bridge/events",
        alias="BRIDGE_GATEWAY_EVENTS_PATH",
        description="Tunnel Gateway SSE events path (internal)",
    )
    bridge_agent_token_expire_days: int = Field(
        365,
        alias="BRIDGE_AGENT_TOKEN_EXPIRE_DAYS",
        description="Bridge agent token 过期天数（JWT exp）",
        ge=1,
        le=3650,
    )

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

    # Content moderation / redaction
    enable_content_moderation: bool = Field(
        True,
        alias="ENABLE_CONTENT_MODERATION",
        description="是否启用请求/响应的敏感信息检测与脱敏流水线",
    )
    content_moderation_action: str = Field(
        "mask",
        alias="CONTENT_MODERATION_ACTION",
        description="内容审核策略：log/mask/block",
    )
    content_moderation_mask_token: str = Field(
        "***REDACTED***",
        alias="CONTENT_MODERATION_MASK_TOKEN",
        description="敏感信息打码时使用的占位符",
    )
    content_moderation_mask_response: bool = Field(
        True,
        alias="CONTENT_MODERATION_MASK_RESPONSE",
        description="是否对返回给调用方的响应内容也做打码",
    )
    content_moderation_mask_stream: bool = Field(
        True,
        alias="CONTENT_MODERATION_MASK_STREAM",
        description="是否在流式响应中对敏感片段做打码（若 action=mask）",
    )

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
    log_dir: str = Field(
        "logs",
        alias="LOG_DIR",
        description="日志目录（相对路径以 backend 项目根目录为基准）；默认 logs",
    )
    log_backup_days: int = Field(
        7,
        alias="LOG_BACKUP_DAYS",
        description="保留最近 N 天的日志目录；0 表示不清理",
        ge=0,
    )
    log_split_by_business: bool = Field(
        True,
        alias="LOG_SPLIT_BY_BUSINESS",
        description="是否按业务/模块拆分日志文件（按调用文件路径推断）；默认开启",
    )

    # Secret key for hashing/encrypting sensitive data (e.g. key preference hash).
    secret_key: str = Field(
        "please-change-me",
        alias="SECRET_KEY",
        description="Secret key used to derive hashed identifiers for API keys; please override in production",
    )

    # JWT RSA Keys
    jwt_private_key_path: str = Field(
        "security/private.pem",
        alias="JWT_PRIVATE_KEY_PATH",
        description="Path to the RSA private key for JWT signing",
    )
    jwt_public_key_path: str = Field(
        "security/public.pem",
        alias="JWT_PUBLIC_KEY_PATH",
        description="Path to the RSA public key for JWT verification",
    )

    @property
    def jwt_private_key(self) -> str:
        try:
            with open(self.jwt_private_key_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback for dev/test if keys don't exist (though they should)
            return ""

    @property
    def jwt_public_key(self) -> str:
        try:
            with open(self.jwt_public_key_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return ""

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
        description="（Legacy）旧版基础计费单价，当前计费统一由 ProviderModel.pricing 决定",
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
    enable_streaming_precharge: bool = Field(
        False,
        alias="ENABLE_STREAMING_PRECHARGE",
        description="是否在流式请求开始前做积分预扣（默认关闭）",
    )
    credits_auto_topup_interval_seconds: int = Field(
        24 * 60 * 60,
        alias="CREDITS_AUTO_TOPUP_INTERVAL_SECONDS",
        description="自动积分充值任务执行间隔（单位：秒），默认每日一次",
        ge=60,
    )

    # Chat context window (assistant conversation mode)
    chat_context_max_messages: int = Field(
        50,
        alias="CHAT_CONTEXT_MAX_MESSAGES",
        description="会话模式下构建上游 messages 时最多携带的历史消息条数（不含 system；不含本次新 user 消息）。0 表示不限制。",
        ge=0,
        le=1000,
    )

    # User avatar storage configuration
    avatar_local_dir: str = Field(
        default=str(_project_root / "backend" / "media" / "avatars"),
        alias="AVATAR_LOCAL_DIR",
        description="用户头像在本地磁盘上的存储目录（默认在项目 backend/media/avatars 下）",
    )
    avatar_local_base_url: str = Field(
        default="/media/avatars",
        alias="AVATAR_LOCAL_BASE_URL",
        description="本地头像文件对外访问的 URL 前缀，例如 /media/avatars",
    )
    avatar_oss_base_url: str | None = Field(
        default=None,
        alias="AVATAR_OSS_BASE_URL",
        description=(
            "当管理员配置了 OSS 时，填写 OSS Bucket 的基础访问 URL "
            "（例如 https://bucket.oss-cn-hangzhou.aliyuncs.com）；"
            "此时用户头像只在数据库中保存对象 key，完整访问 URL 在读取时按该前缀拼接。"
        ),
    )

    # Generated images (text-to-image) OSS storage configuration
    image_storage_provider: Literal["aliyun_oss", "s3"] = Field(
        default="aliyun_oss",
        alias="IMAGE_STORAGE_PROVIDER",
        description="对象存储提供商，支持 aliyun_oss（默认）或 s3（AWS/MinIO/Cloudflare R2 等兼容接口）",
    )
    image_oss_endpoint: str | None = Field(
        default=None,
        alias="IMAGE_OSS_ENDPOINT",
        description="对象存储 Endpoint；阿里 OSS 形如 https://oss-cn-hangzhou.aliyuncs.com；S3/R2 可填兼容 Endpoint",
    )
    image_oss_region: str | None = Field(
        default=None,
        alias="IMAGE_OSS_REGION",
        description="S3/R2 兼容接口的 region（阿里 OSS 可留空）",
    )
    image_oss_bucket: str | None = Field(
        default=None,
        alias="IMAGE_OSS_BUCKET",
        description="对象存储 Bucket 名称（建议私有读）",
    )
    image_oss_access_key_id: str | None = Field(
        default=None,
        alias="IMAGE_OSS_ACCESS_KEY_ID",
        description="对象存储 AccessKeyId（用于后端上传与读取对象）",
    )
    image_oss_access_key_secret: str | None = Field(
        default=None,
        alias="IMAGE_OSS_ACCESS_KEY_SECRET",
        description="对象存储 AccessKeySecret（用于后端上传与读取对象）",
    )
    image_oss_prefix: str = Field(
        default="generated-images",
        alias="IMAGE_OSS_PREFIX",
        description="文生图对象 key 前缀，例如 generated-images",
    )
    image_signed_url_ttl_seconds: int = Field(
        default=60 * 60,
        alias="IMAGE_SIGNED_URL_TTL_SECONDS",
        description="网关短链 URL 有效期（秒），用于文生图 response_format=url",
        ge=60,
        le=7 * 24 * 60 * 60,
    )

    @property
    def enable_security_middleware(self) -> bool:
        """
        是否启用安全相关中间件栈。
        默认仅在 APP_ENV=production 时开启，可通过 ENABLE_SECURITY_MIDDLEWARE 显式覆盖。
        """
        if self.security_middleware_override is not None:
            return self.security_middleware_override
        return self.environment.lower() == "production"

    @property
    def enable_api_docs(self) -> bool:
        """
        是否启用 FastAPI 内置文档相关路由（/docs、/redoc、/openapi.json）。
        默认仅在非生产环境开启，可通过 ENABLE_API_DOCS 显式覆盖。
        """
        if self.api_docs_override is not None:
            return self.api_docs_override
        return self.environment.lower() != "production"

_WEAK_SECRET_KEY_VALUES = {
    "please-change-me",
    "change-me-secret-key",
    "your-secret-key",
}
_MIN_SECRET_KEY_LENGTH = 32


def _validate_production_secret_key(cfg: Settings) -> None:
    if cfg.environment.lower() != "production":
        return

    secret_key = (cfg.secret_key or "").strip()
    if not secret_key:
        raise RuntimeError(
            "APP_ENV=production 时必须设置 SECRET_KEY；"
            "请使用 POST /system/secret-key/generate 生成随机值并写入 .env。"
        )

    lowered = secret_key.lower()
    if secret_key in _WEAK_SECRET_KEY_VALUES or "please-change-me" in lowered or "change-me" in lowered:
        raise RuntimeError(
            "检测到不安全的 SECRET_KEY 默认/占位符；"
            "生产环境请使用 POST /system/secret-key/generate 生成强随机值并写入 .env。"
        )

    if len(secret_key) < _MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY 长度过短（需至少 {_MIN_SECRET_KEY_LENGTH} 字符）；"
            "生产环境请使用 POST /system/secret-key/generate 生成强随机值。"
        )


settings = Settings()  # Reads from environment if available
_validate_production_secret_key(settings)


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
