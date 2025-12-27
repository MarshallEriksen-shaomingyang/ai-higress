from __future__ import annotations

import pathlib
import sys

import sqlalchemy as sa
from alembic.config import Config as AlembicConfig
from sqlalchemy import engine_from_config, pool

from alembic import context

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.models import Base  # noqa: E402
from app.settings import settings  # noqa: E402

target_metadata = Base.metadata


def _ensure_alembic_version_num_length(connection: sa.Connection, length: int = 128) -> None:
    """
    兼容历史数据库：alembic_version.version_num 早期可能是 VARCHAR(32)，
    当 revision id 长于 32（例如 0006_add_api_key_provider_restrictions）会导致迁移在更新版本号时直接失败。
    这里在跑迁移前自动扩容到更安全的长度，避免“初次部署/旧库升级”卡在很早期的版本更新阶段。
    """
    if connection.dialect.name != "postgresql":
        return

    try:
        current_len = connection.execute(
            sa.text(
                """
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'alembic_version'
                  AND column_name = 'version_num'
                ORDER BY table_schema
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
    except Exception:
        # 表不存在/权限不足等情况：交给 Alembic 正常创建或后续报错处理
        return

    if current_len is None or current_len >= length:
        return

    connection.execute(
        sa.text(f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({int(length)})")
    )


def _configure_alembic() -> AlembicConfig:
    """
    确保 Alembic Config 始终使用 settings.database_url。
    仅在 Alembic CLI 运行时被调用，此时 context 已初始化。
    """
    cfg = context.config
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    cfg = _configure_alembic()
    context.configure(
        url=cfg.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version",
        version_column="version_num",
        version_column_type=sa.String(length=128),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    cfg = _configure_alembic()
    connectable = engine_from_config(
        cfg.get_section(cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _ensure_alembic_version_num_length(connection, length=128)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version",
            version_column="version_num",
            version_column_type=sa.String(length=128),
        )

        with context.begin_transaction():
            context.run_migrations()


def _in_alembic_context() -> bool:
    """
    当 env.py 被普通 Python 代码 import 时，context 未初始化会抛异常。
    Alembic 1.12+ 在 EnvironmentContext 创建后，但在 configure 之前
    context.get_context() 会直接报错，导致迁移被跳过。改用
    context.is_offline_mode() 来探测是否处于 Alembic CLI 环境。
    """
    try:
        context.is_offline_mode()
        return True
    except (NameError, Exception):
        return False


if _in_alembic_context():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
