from __future__ import annotations

"""
Celery 应用实例。

该模块集中管理 Celery 配置，供 worker / beat 进程复用。
默认使用 Redis 作为 broker 和 result backend，具体连接信息通过 .env 中的
CELERY_BROKER_URL / CELERY_RESULT_BACKEND 进行配置。

使用方式（在 backend 目录下）::

    # 启动 worker
    celery -A app.celery_app.celery_app worker -l info

    # 启动 beat（如需定时任务）
    celery -A app.celery_app.celery_app beat -l info
"""

from celery import Celery
from celery.signals import beat_init, worker_process_init

from app.logging_config import setup_logging
from app.settings import settings

celery_app = Celery(
    "apiproxy",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_default_queue=settings.celery_task_default_queue,
    timezone=settings.celery_timezone,
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 显式导入子模块里的任务，避免 worker 只加载 app.tasks/__init__.py 而漏掉 registration.* 等任务。
    imports=(
        "app.tasks",
        "app.tasks.chat_run",
        "app.tasks.image_generation_run",
        "app.tasks.registration",
        "app.tasks.conversation_title",
        "app.tasks.api_key_health",
        "app.tasks.session_maintenance",
        "app.tasks.credit_billing",
        "app.tasks.credit_auto_topup",
        "app.tasks.provider_audit",
        "app.tasks.user_probe",
        "app.tasks.upstream_proxy_pool",
        "app.tasks.model_catalog",
        "app.metrics.tasks",
    ),
)

# 自动发现 app 包下的 tasks 模块（即 app.tasks）。
# 注意：Celery 默认是“惰性发现”，在仅导入 celery_app（不启动 worker）时不会立即导入任务模块，
# 这会导致测试环境下看不到自定义任务。这里强制立即发现与导入，确保 tasks.* 已注册。
celery_app.autodiscover_tasks(["app"], force=True)
celery_app.loader.import_default_modules()


@worker_process_init.connect
def init_worker_logging(**kwargs):
    """
    在 Celery worker 进程初始化时配置应用日志。
    
    这确保任务执行时的 logger.info/debug/error 等调用能正确输出到控制台和日志文件。
    """
    setup_logging()


@beat_init.connect
def init_beat_logging(**kwargs):
    """
    在 Celery beat 进程初始化时配置应用日志。
    
    这确保定时任务调度器的日志能正确输出。
    """
    setup_logging()


__all__ = ["celery_app"]
