from __future__ import annotations

import base64
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.logging_config import logger
from app.services.api_key_cache import cache_api_key_sync
from app.services.key_management_service import initialize_system_admin
from app.services.user_service import has_any_user

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@example.com"


@dataclass
class BootstrapAdminResult:
    username: str
    email: str
    password: str
    api_key_token: str
    api_key_token_base64: str


def ensure_initial_admin(session: Session) -> BootstrapAdminResult | None:
    """
    Create the very first superuser and API key if the database is empty.
    使用统一的密钥管理服务替代手动创建过程。
    """
    if has_any_user(session):
        return None

    try:
        # 使用统一的密钥管理服务初始化管理员
        admin_credentials = initialize_system_admin(
            session=session,
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_EMAIL,
            display_name="Administrator",
        )
        
        # 获取API密钥并缓存
        from app.services.api_key_service import list_api_keys_for_user
        api_keys = list_api_keys_for_user(session, admin_credentials["username"])
        if api_keys:
            cache_api_key_sync(api_keys[0])
        
        token = admin_credentials["api_key"]
        token_base64 = base64.b64encode(token.encode("utf-8")).decode("ascii")
        
        logger.warning(
            "已自动创建初始管理员账号，请立即登录并修改凭证 | username=%s email=%s password=%s api_key_token=%s api_key_token_base64=%s",
            admin_credentials["username"],
            admin_credentials["email"],
            admin_credentials["password"],
            token,
            token_base64,
        )
        
        return BootstrapAdminResult(
            username=admin_credentials["username"],
            email=admin_credentials["email"],
            password=admin_credentials["password"],
            api_key_token=token,
            api_key_token_base64=token_base64,
        )
    except Exception as exc:
        logger.error(f"Failed to bootstrap admin: {exc}")
        raise


__all__ = ["BootstrapAdminResult", "ensure_initial_admin"]
