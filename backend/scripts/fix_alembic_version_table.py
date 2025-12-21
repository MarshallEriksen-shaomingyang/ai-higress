#!/usr/bin/env python3
"""
修复 alembic_version 表的 version_num 字段长度问题。

Alembic 默认创建的 version_num 字段是 VARCHAR(32)，
但项目中的迁移版本号最长达到 51 字符，导致迁移失败。

此脚本会：
1. 检查 alembic_version 表是否存在
2. 如果不存在，创建一个 version_num 为 VARCHAR(64) 的表
3. 如果存在但字段长度不够，修改字段长度
"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, inspect, text

from app.settings import settings


def main():
    """主函数"""
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)

    with engine.begin() as conn:
        # 检查表是否存在
        if "alembic_version" in inspector.get_table_names():
            print("✓ alembic_version 表已存在")

            # 检查字段长度
            result = conn.execute(text("""
                SELECT character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name='alembic_version' 
                AND column_name='version_num'
            """))
            current_length = result.scalar()

            if current_length and current_length < 64:
                print(f"⚠ 当前 version_num 字段长度: {current_length}，需要扩展到 64")
                conn.execute(text("""
                    ALTER TABLE alembic_version 
                    ALTER COLUMN version_num TYPE VARCHAR(64)
                """))
                print("✓ 字段长度已扩展到 VARCHAR(64)")
            else:
                print(f"✓ version_num 字段长度已足够: {current_length}")
        else:
            print("⚠ alembic_version 表不存在，正在创建...")
            conn.execute(text("""
                CREATE TABLE alembic_version (
                    version_num VARCHAR(64) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))
            print("✓ alembic_version 表已创建 (version_num VARCHAR(64))")

    print("\n✓ 修复完成！现在可以运行 'alembic upgrade head' 了")


if __name__ == "__main__":
    main()
