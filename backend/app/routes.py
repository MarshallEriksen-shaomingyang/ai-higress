import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.auth_routes import router as auth_router
from .api.logical_model_routes import router as logical_model_router
from .api.metrics_dashboard_v2_routes import router as metrics_dashboard_v2_router
from .api.metrics_routes import router as metrics_router
from .api.provider_preset_routes import router as provider_preset_router
from .api.provider_routes import router as provider_router
from .api.routing_routes import router as routing_router
from .api.session_routes import router as session_router
from .api.system_routes import router as system_router
from .api.v1.admin_eval_routes import router as admin_eval_router
from .api.v1.admin_notification_routes import router as admin_notification_router
from .api.v1.admin_provider_preset_routes import (
    router as admin_provider_preset_router,
)
from .api.v1.admin_provider_routes import router as admin_provider_router
from .api.v1.admin_registration_routes import router as admin_registration_router
from .api.v1.admin_role_routes import router as admin_role_router
from .api.v1.admin_upstream_proxy_routes import router as admin_upstream_proxy_router
from .api.v1.admin_user_permission_routes import (
    router as admin_user_permission_router,
)
from .api.v1.admin_user_routes import router as admin_user_router
from .api.v1.api_key_routes import router as api_key_router
from .api.v1.assistant_routes import router as assistant_router
from .api.v1.bridge_routes import router as bridge_router
from .api.v1.chat_routes import router as chat_router
from .api.v1.cli_config import router as cli_config_router
from .api.v1.credit_routes import router as credit_router
from .api.v1.eval_routes import router as eval_router
from .api.v1.gateway_routes import router as gateway_router
from .api.v1.notification_routes import router as notification_router
from .api.v1.private_provider_routes import router as private_provider_router
from .api.v1.project_chat_settings_routes import router as project_chat_settings_router
from .api.v1.project_eval_config_routes import router as project_eval_config_router
from .api.v1.provider_key_routes import router as provider_key_router
from .api.v1.provider_submission_routes import (
    router as provider_submission_router,
)
from .api.v1.session_routes import router as user_session_router
from .api.v1.user_provider_routes import router as user_provider_router
from .api.v1.user_routes import router as user_router
from .db import SessionLocal
from .log_sanitizer import sanitize_headers_for_log
from .logging_config import logger
from .services.avatar_service import ensure_avatar_storage_dir
from .services.bootstrap_admin import ensure_initial_admin


async def handle_unexpected_error(request: Request, exc: Exception):
    """
    全局异常处理器，统一返回结构化错误响应并打印日志。
    """

    error_id = uuid.uuid4().hex
    logger.exception(
        "Unhandled error %s %s (error_id=%s)",
        request.method,
        request.url.path,
        error_id,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "internal_error",
            "message": "服务器内部错误，请稍后再试",
            "error_id": error_id,
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - startup: 执行数据库迁移、确保初始管理员账号存在
    - shutdown: 目前无额外清理逻辑
    """
    from app.db.migration_runner import auto_upgrade_database

    session = SessionLocal()
    try:
        # 执行数据库迁移（仅在显式启用时）
        auto_upgrade_database()
        # 确保初始管理员账号存在
        ensure_initial_admin(session)
    finally:
        session.close()

    # 让应用继续启动并处理请求
    yield

    # 这里可以按需添加关闭时清理逻辑


def create_app() -> FastAPI:
    from fastapi.middleware.cors import CORSMiddleware

    from app.middleware import (
        RateLimitMiddleware,
        RequestValidatorMiddleware,
        SecurityHeadersMiddleware,
    )

    from .settings import settings

    # 解析 CORS 配置
    cors_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",")] if settings.cors_allow_origins else []
    cors_methods = [method.strip() for method in settings.cors_allow_methods.split(",")] if settings.cors_allow_methods != "*" else ["*"]
    cors_headers = [header.strip() for header in settings.cors_allow_headers.split(",")] if settings.cors_allow_headers != "*" else ["*"]

    docs_url = "/docs" if settings.enable_api_docs else None
    redoc_url = "/redoc" if settings.enable_api_docs else None
    openapi_url = "/openapi.json" if settings.enable_api_docs else None

    # 使用 lifespan 替代 on_event("startup")
    app = FastAPI(
        title="AI Gateway",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.add_exception_handler(Exception, handle_unexpected_error)

    if not settings.enable_api_docs:
        logger.info(
            "API docs routes are disabled (environment=%s); set ENABLE_API_DOCS=true to enable.",
            settings.environment,
        )

    # 安全相关中间件：仅在生产环境启用
    if settings.enable_security_middleware:
        logger.info(
            "Enabling security middleware stack (environment=%s)",
            settings.environment,
        )
        app.add_middleware(
            SecurityHeadersMiddleware,
            enable_hsts=False,  # 开发环境关闭 HSTS，生产环境建议开启
        )

        app.add_middleware(
            RateLimitMiddleware,
            redis_client=None,  # 使用内存存储，生产环境建议传入 Redis 客户端
            # 默认使用 gateway_max_concurrent_requests 作为每分钟请求上限，
            # 可以在 /system/gateway-config 中动态调整。
            default_max_requests=settings.gateway_max_concurrent_requests,
            default_window_seconds=60,
            path_limits={
                "/auth/login": (5, 60),  # 登录接口：每分钟 5 次
                "/auth/register": (3, 300),  # 注册接口：每 5 分钟 3 次
            },
        )

        app.add_middleware(
            RequestValidatorMiddleware,
            enable_sql_injection_check=True,
            enable_xss_check=True,
            enable_path_traversal_check=True,
            enable_command_injection_check=True,
            enable_user_agent_check=True,
            log_suspicious_requests=True,
            # 暂时关闭请求体扫描，避免大包体/文件上传被误判，后续按需再开启
            inspect_body=False,
            ban_ip_on_detection=True,
            ban_ttl_seconds=900,
        )
    else:
        logger.warning(
            "Security middleware stack is disabled (environment=%s); "
            "set APP_ENV=production to enable in production.",
            settings.environment,
        )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=cors_methods,
        allow_headers=cors_headers,
    )

    # 用户头像等本地静态文件挂载
    avatar_dir = ensure_avatar_storage_dir()
    app.mount(
        settings.avatar_local_base_url,
        StaticFiles(directory=str(avatar_dir), check_dir=True),
        name="avatars",
    )

    # 业务路由挂载
    # 认证与系统管理
    app.include_router(auth_router)
    app.include_router(system_router)

    # Provider 管理与逻辑模型 / 路由
    # 注意：provider_submission_router 必须在 provider_router 之前挂载，
    # 以避免 /providers/{provider_id} 抢占 /providers/submissions 路由。
    app.include_router(provider_submission_router)
    app.include_router(provider_router)
    app.include_router(provider_preset_router)
    app.include_router(logical_model_router)
    app.include_router(routing_router)
    app.include_router(session_router)

    # Chat 相关网关路由（/v1/chat/completions、/v1/responses、/v1/messages）
    app.include_router(chat_router)
    # MCP Bridge（Agent / Tools / Events）
    app.include_router(bridge_router)

    # Metrics
    app.include_router(metrics_router)
    app.include_router(metrics_dashboard_v2_router)

    # 用户与 API Key 管理
    app.include_router(user_router)
    app.include_router(notification_router)
    app.include_router(api_key_router)
    app.include_router(provider_key_router)
    app.include_router(user_session_router)
    app.include_router(credit_router)

    # Chat 应用能力：助手 / 会话 / 评测闭环（JWT）
    app.include_router(assistant_router)
    app.include_router(eval_router)
    app.include_router(project_eval_config_router)
    app.include_router(project_chat_settings_router)

    # 用户私有 Provider
    app.include_router(private_provider_router)
    app.include_router(user_provider_router)

    # CLI 配置脚本
    app.include_router(cli_config_router)

    # 管理端路由
    app.include_router(admin_role_router)
    app.include_router(admin_user_permission_router)
    app.include_router(admin_user_router)
    app.include_router(admin_provider_router)
    app.include_router(admin_provider_preset_router)
    app.include_router(admin_registration_router)
    app.include_router(admin_notification_router)
    app.include_router(admin_eval_router)
    app.include_router(admin_upstream_proxy_router)

    # 基础网关路由（health/models/context 等）
    app.include_router(gateway_router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        基础请求日志中间件，记录请求和响应状态。
        会对 Authorization / x-api-key / cookie 等敏感头做脱敏处理。
        """

        client_host = request.client.host if request.client else "-"
        headers_for_log = sanitize_headers_for_log(request.headers)

        logger.info(
            "HTTP %s %s from %s, headers=%s",
            request.method,
            request.url.path,
            client_host,
            headers_for_log,
        )
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised via tests
            response = await handle_unexpected_error(request, exc)
        logger.info(
            "HTTP %s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    return app
