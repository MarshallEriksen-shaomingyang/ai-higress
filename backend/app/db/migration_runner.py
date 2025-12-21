from __future__ import annotations

import threading
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.logging_config import logger
from app.settings import settings

_MIGRATION_LOCK = threading.Lock()
_MIGRATION_APPLIED = False


def _should_auto_apply() -> bool:
    """
    仅在 Postgres 数据库上自动执行迁移，避免在测试用的 SQLite/内存库上运行。
    需要显式设置环境变量 ENABLE_AUTO_MIGRATION=true 才会执行，避免循环导入。
    """
    import os
    if not settings.auto_apply_db_migrations:
        return False
    if not os.getenv("ENABLE_AUTO_MIGRATION", "").lower() == "true":
        return False
    url = settings.database_url.lower()
    if url.startswith("sqlite"):
        return False
    # 仅支持 Postgres（postgres / postgresql）
    return url.startswith("postgres")


def _build_alembic_config(base_dir: Path) -> Config:
    config_path = base_dir / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(base_dir / "alembic"))
    # pytest 或 CLI 命令可能在仓库根目录运行，此时 Alembic 默认的
    # version_locations="alembic/versions" 会被解析为相对于当前 cwd 的路径，
    # 导致无法定位最新的 revision（例如 0027_add_probe_settings）。
    # 将路径改成绝对值后即可在任意工作目录执行 `alembic upgrade`。
    cfg.set_main_option("version_locations", str(base_dir / "alembic" / "versions"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def auto_upgrade_database() -> None:
    """
    在进程启动时确保数据库 schema 升级到最新版本，避免缺失列导致任务异常。
    该逻辑仅执行一次，并且只针对 Postgres 数据库运行。
    """
    global _MIGRATION_APPLIED
    if _MIGRATION_APPLIED or not _should_auto_apply():
        return

    with _MIGRATION_LOCK:
        if _MIGRATION_APPLIED:
            return

        backend_dir = Path(__file__).resolve().parents[2]
        alembic_ini = backend_dir / "alembic.ini"
        if not alembic_ini.exists():
            logger.warning(
                "Alembic 配置文件 %s 不存在，跳过自动迁移。请确认部署环境是否包含迁移脚本。",
                alembic_ini,
            )
            _MIGRATION_APPLIED = True
            return

        logger.info("自动执行 Alembic 迁移，确保数据库 schema 为最新版本...")
        try:
            config = _build_alembic_config(backend_dir)
            command.upgrade(config, "head")
        except Exception:
            logger.exception(
                "自动执行 Alembic 迁移失败，请手动运行 'alembic upgrade head'。"
            )
            raise
        else:
            logger.info("数据库迁移完成。")
            _MIGRATION_APPLIED = True
