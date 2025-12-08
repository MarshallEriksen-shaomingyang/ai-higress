import argparse
import sys
from pathlib import Path

# 确保可从仓库根或 backend 目录运行
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # type: ignore  # noqa: E402
from app.models import User  # type: ignore  # noqa: E402
from app.services.jwt_auth_service import hash_password  # type: ignore  # noqa: E402
from app.services.key_management_service import (  # type: ignore  # noqa: E402
    generate_secure_random_password,
)


def reset_password(email: str, password: str | None) -> int:
    """Reset password for the given email; auto-generate if not provided."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if user is None:
            print(f"未找到用户: {email}")
            return 1

        new_password = password or generate_secure_random_password()
        user.hashed_password = hash_password(new_password)
        db.add(user)
        db.commit()
        print(
            "密码已重置，记录好新密码后尽快登录并更新：\n"
            f"  email: {email}\n"
            f"  password: {new_password}"
        )
        return 0
    except Exception as exc:  # pragma: no cover - 管理脚本兜底
        db.rollback()
        print(f"重置失败: {exc}")
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="为指定邮箱的用户重置密码（管理员忘记密码时使用）"
    )
    parser.add_argument("--email", required=True, help="目标用户邮箱（管理员邮箱）")
    parser.add_argument(
        "--password",
        help="新密码；不提供则自动生成强密码",
    )
    args = parser.parse_args()
    return reset_password(args.email, args.password)


if __name__ == "__main__":
    sys.exit(main())
