from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.logging_config import logger
from app.services.key_management_service import initialize_system_admin
from app.services.user_service import has_any_user
from app.settings import settings


@dataclass
class BootstrapAdminResult:
    username: str
    email: str
    password: str


def ensure_initial_admin(session: Session) -> BootstrapAdminResult | None:
    """
    Create the very first superuser if the database is empty.
    使用统一的密钥管理服务替代手动创建过程。
    """
    if has_any_user(session):
        return None

    try:
        # 使用统一的密钥管理服务初始化管理员
        admin_credentials = initialize_system_admin(
            session=session,
            username=settings.default_admin_username,
            email=settings.default_admin_email,
            display_name="Administrator",
        )

        logger.warning(
            "已自动创建初始管理员账号，请立即登录并修改凭证 | username=%s email=%s password=%s",
            admin_credentials["username"],
            admin_credentials["email"],
            admin_credentials["password"],
        )

        return BootstrapAdminResult(
            username=admin_credentials["username"],
            email=admin_credentials["email"],
            password=admin_credentials["password"],
        )
    except Exception as exc:
        logger.error(f"Failed to bootstrap admin: {exc}")
        raise


__all__ = ["BootstrapAdminResult", "ensure_initial_admin"]
