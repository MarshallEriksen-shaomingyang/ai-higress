from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from .api.auth_routes import router as auth_router
from .api.logical_model_routes import router as logical_model_router
from .api.metrics_routes import router as metrics_router
from .api.provider_preset_routes import router as provider_preset_router
from .api.provider_routes import router as provider_router
from .api.routing_routes import router as routing_router
from .api.session_routes import router as session_router
from .api.system_routes import router as system_router
from .api.v1.admin_provider_preset_routes import (
    router as admin_provider_preset_router,
)
from .api.v1.admin_provider_routes import router as admin_provider_router
from .api.v1.admin_role_routes import router as admin_role_router
from .api.v1.admin_user_permission_routes import (
    router as admin_user_permission_router,
)
from .api.v1.admin_registration_routes import router as admin_registration_router
from .api.v1.api_key_routes import router as api_key_router
from .api.v1.chat_routes import router as chat_router
from .api.v1.credit_routes import router as credit_router
from .api.v1.gateway_routes import router as gateway_router
from .api.v1.private_provider_routes import router as private_provider_router
from .api.v1.provider_key_routes import router as provider_key_router
from .api.v1.provider_submission_routes import (
    router as provider_submission_router,
)
from .api.v1.user_provider_routes import router as user_provider_router
from .api.v1.session_routes import router as user_session_router
from .api.v1.user_routes import router as user_router
from .db import SessionLocal
from .logging_config import logger
from .services.bootstrap_admin import ensure_initial_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - startup: 确保初始管理员账号存在
    - shutdown: 目前无额外清理逻辑
    """
    session = SessionLocal()
    try:
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

    # 使用 lifespan 替代 on_event("startup")
    app = FastAPI(title="AI Gateway", version="0.1.0", lifespan=lifespan)

    # 安全相关中间件
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=False,  # 开发环境关闭 HSTS，生产环境建议开启
    )

    app.add_middleware(
        RateLimitMiddleware,
        redis_client=None,  # 使用内存存储，生产环境建议传入 Redis 客户端
        default_max_requests=100,  # 默认每分钟 100 次请求
        default_window_seconds=60,
        path_limits={
            "/auth/login": (5, 60),  # 登录接口：每分钟 5 次
            "/auth/register": (3, 300),  # 注册接口：每 5 分钟 3 次
            "/v1/chat/completions": (60, 60),  # Chat 接口：每分钟 60 次
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
        inspect_body=True,
        ban_ip_on_detection=True,
        ban_ttl_seconds=900,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 业务路由挂载
    # 认证与系统管理
    app.include_router(auth_router)
    app.include_router(system_router)

    # Provider 管理与逻辑模型 / 路由
    app.include_router(provider_router)
    app.include_router(provider_preset_router)
    app.include_router(logical_model_router)
    app.include_router(routing_router)
    app.include_router(session_router)

    # Chat 相关网关路由（/v1/chat/completions 等）
    app.include_router(chat_router)

    # Metrics
    app.include_router(metrics_router)

    # 用户与 API Key 管理
    app.include_router(user_router)
    app.include_router(api_key_router)
    app.include_router(provider_key_router)
    app.include_router(user_session_router)
    app.include_router(credit_router)

    # 用户私有 Provider 与投稿
    app.include_router(private_provider_router)
    app.include_router(user_provider_router)
    app.include_router(provider_submission_router)

    # 管理端路由
    app.include_router(admin_role_router)
    app.include_router(admin_user_permission_router)
    app.include_router(admin_provider_router)
    app.include_router(admin_provider_preset_router)
    app.include_router(admin_registration_router)

    # 基础网关路由（health/models/context 等）
    app.include_router(gateway_router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        基础请求日志中间件，记录请求和响应状态。
        会对 Authorization 头做脱敏处理。
        """

        client_host = request.client.host if request.client else "-"
        headers_for_log: dict[str, str] = {}
        for k, v in request.headers.items():
            if k.lower() == "authorization":
                headers_for_log[k] = "***REDACTED***"
            else:
                headers_for_log[k] = v

        logger.info(
            "HTTP %s %s from %s, headers=%s",
            request.method,
            request.url.path,
            client_host,
            headers_for_log,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error while processing %s %s",
                request.method,
                request.url.path,
            )
            raise
        logger.info(
            "HTTP %s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    return app
