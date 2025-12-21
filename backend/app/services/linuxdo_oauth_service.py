from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - fallback when redis is missing
    Redis = object  # type: ignore[misc,assignment]

from app.logging_config import logger
from app.models import Identity, User
from app.redis_client import redis_delete, redis_get_json, redis_set_json
from app.services.credit_service import get_or_create_account_for_user
from app.services.key_management_service import generate_secure_random_password
from app.services.registration_window_service import (
    RegistrationQuotaExceededError,
    RegistrationWindowClosedError,
    RegistrationWindowNotFoundError,
    claim_registration_slot,
    rollback_registration_slot,
)
from app.services.user_service import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    assign_default_role,
    create_user,
)
from app.settings import settings

LINUXDO_PROVIDER = "linuxdo"
STATE_STORAGE_KEY = "auth:oauth:linuxdo:state:{state}"
STATE_TTL_SECONDS = 300


class LinuxDoOAuthError(Exception):
    """Base error for LinuxDo OAuth failures."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LinuxDoToken:
    access_token: str
    token_type: str
    expires_in: int | None


@dataclass
class LinuxDoUserProfile:
    external_id: str
    username: str | None
    display_name: str | None
    avatar_url: str | None
    is_active: bool


def _ensure_oauth_enabled() -> None:
    if not getattr(settings, "linuxdo_enabled", False):
        raise LinuxDoOAuthError(
            "LinuxDo OAuth 尚未启用",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    required = {
        "LINUXDO_CLIENT_ID": settings.linuxdo_client_id,
        "LINUXDO_CLIENT_SECRET": settings.linuxdo_client_secret,
        "LINUXDO_REDIRECT_URI": settings.linuxdo_redirect_uri,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise LinuxDoOAuthError(
            f"LinuxDo OAuth 配置缺失: {', '.join(missing)}",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


async def build_linuxdo_authorize_url(redis: Redis) -> str:
    """
    生成带 state 的授权地址，并把 state 暂存到 Redis。
    """

    _ensure_oauth_enabled()

    state = secrets.token_urlsafe(32)
    state_key = STATE_STORAGE_KEY.format(state=state)
    await redis_set_json(
        redis,
        state_key,
        {"provider": LINUXDO_PROVIDER, "created_at": datetime.now(UTC).isoformat()},
        ttl_seconds=STATE_TTL_SECONDS,
    )

    base_url = httpx.URL(settings.linuxdo_authorize_endpoint)
    params = dict(base_url.params)
    params.update(
        {
            "client_id": settings.linuxdo_client_id,
            "redirect_uri": settings.linuxdo_redirect_uri,
            "response_type": "code",
            "state": state,
        }
    )
    authorize_url = base_url.copy_with(params=params)
    return str(authorize_url)


async def complete_linuxdo_oauth_flow(
    db: Session,
    redis: Redis,
    client: httpx.AsyncClient,
    *,
    code: str,
    state: str | None,
) -> tuple[User, bool]:
    """
    校验 state、换取 LinuxDo 用户信息，并与本地用户同步。
    """

    _ensure_oauth_enabled()
    if not code:
        raise LinuxDoOAuthError("缺少授权码参数")
    if not state:
        raise LinuxDoOAuthError("缺少 state 参数")

    await _consume_state(redis, state)

    token = await _exchange_code_for_token(client, code)
    profile = await _fetch_user_profile(client, token.access_token)
    return _sync_user_from_profile(db, profile)


async def _consume_state(redis: Redis, state: str) -> None:
    """
    获取并删除 state，防止重放。
    """

    state_key = STATE_STORAGE_KEY.format(state=state)
    stored = await redis_get_json(redis, state_key)
    await redis_delete(redis, state_key)

    if not stored or stored.get("provider") != LINUXDO_PROVIDER:
        raise LinuxDoOAuthError("state 无效或已过期")


async def _exchange_code_for_token(client: httpx.AsyncClient, code: str) -> LinuxDoToken:
    """
    调用 LinuxDo token 接口，换取访问令牌。
    """

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.linuxdo_redirect_uri,
        "client_id": settings.linuxdo_client_id,
        "client_secret": settings.linuxdo_client_secret,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = await client.post(
            settings.linuxdo_token_endpoint,
            data=data,
            headers=headers,
        )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise LinuxDoOAuthError(
            f"LinuxDo token 接口请求失败: {exc}",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    if response.status_code >= 400:
        raise LinuxDoOAuthError(
            f"LinuxDo token 接口返回错误状态 {response.status_code}",
            status.HTTP_502_BAD_GATEWAY,
        )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise LinuxDoOAuthError(
            "LinuxDo token 接口返回非 JSON 数据",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    access_token = payload.get("access_token")
    if not isinstance(access_token, str):
        raise LinuxDoOAuthError(
            "LinuxDo token 接口缺少 access_token",
            status.HTTP_502_BAD_GATEWAY,
        )

    token_type = payload.get("token_type") or "Bearer"
    expires_in = payload.get("expires_in")
    expires = None
    if isinstance(expires_in, int):
        expires = expires_in
    else:
        try:
            expires = int(expires_in)
        except Exception:
            expires = None

    return LinuxDoToken(
        access_token=access_token,
        token_type=str(token_type),
        expires_in=expires,
    )


async def _fetch_user_profile(client: httpx.AsyncClient, access_token: str) -> LinuxDoUserProfile:
    """
    拉取 LinuxDo 用户信息。
    """

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = await client.get(
            settings.linuxdo_userinfo_endpoint,
            headers=headers,
        )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise LinuxDoOAuthError(
            f"LinuxDo 用户信息接口请求失败: {exc}",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    if response.status_code >= 400:
        raise LinuxDoOAuthError(
            f"LinuxDo 用户信息接口返回错误状态 {response.status_code}",
            status.HTTP_502_BAD_GATEWAY,
        )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise LinuxDoOAuthError(
            "LinuxDo 用户信息接口返回非 JSON 数据",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    user_payload = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    user_id = user_payload.get("id")
    if user_id is None:
        raise LinuxDoOAuthError(
            "LinuxDo 用户信息缺少 id",
            status.HTTP_502_BAD_GATEWAY,
        )

    username = user_payload.get("username")
    name = user_payload.get("name")
    avatar_template = user_payload.get("avatar_template")
    is_active = user_payload.get("active", True)

    return LinuxDoUserProfile(
        external_id=str(user_id),
        username=str(username) if username else None,
        display_name=str(name) if name else (str(username) if username else None),
        avatar_url=_build_avatar_url(avatar_template),
        is_active=bool(is_active),
    )


def _build_avatar_url(template: Any) -> str | None:
    if not isinstance(template, str):
        return None
    url = template.replace("{size}", "240")
    if url.startswith("//"):
        url = f"https:{url}"
    return url


def _sync_user_from_profile(db: Session, profile: LinuxDoUserProfile) -> tuple[User, bool]:
    """
    根据 LinuxDo profile 获取已有用户或创建新用户。
    """

    identity = (
        db.execute(
            select(Identity).where(
                Identity.provider == LINUXDO_PROVIDER,
                Identity.external_id == profile.external_id,
            )
        )
        .scalars()
        .first()
    )

    if identity:
        user = db.get(User, identity.user_id)
        if user is None:
            logger.warning(
                "Stale LinuxDo identity detected (user missing), removing identity for external_id=%s",
                profile.external_id,
            )
            db.delete(identity)
            db.commit()
        else:
            _apply_profile_updates(db, user, identity, profile)
            return user, False

    user, requires_manual_activation = _create_user_from_profile(db, profile)
    _attach_identity(db, user, profile)
    return user, requires_manual_activation


def _apply_profile_updates(
    db: Session,
    user: User,
    identity: Identity,
    profile: LinuxDoUserProfile,
) -> None:
    changed = False

    if profile.display_name and user.display_name != profile.display_name:
        user.display_name = profile.display_name
        changed = True
    if profile.avatar_url and user.avatar != profile.avatar_url:
        user.avatar = profile.avatar_url
        changed = True
    if user.is_active != profile.is_active:
        user.is_active = profile.is_active
        changed = True

    new_identity_name = profile.username or profile.display_name
    if new_identity_name and identity.display_name != new_identity_name:
        identity.display_name = new_identity_name
        changed = True

    if changed:
        db.add(user)
        db.add(identity)
        db.commit()
        db.refresh(user)


def _create_user_from_profile(db: Session, profile: LinuxDoUserProfile) -> tuple[User, bool]:
    try:
        window = claim_registration_slot(db)
    except (
        RegistrationWindowNotFoundError,
        RegistrationWindowClosedError,
        RegistrationQuotaExceededError,
    ) as exc:
        raise LinuxDoOAuthError(str(exc), status.HTTP_403_FORBIDDEN) from exc

    email = f"{profile.external_id}@linux.do"
    display_name = profile.display_name or profile.username or f"LinuxDo 用户 {profile.external_id}"
    avatar = profile.avatar_url
    password = generate_secure_random_password(24)
    is_active = bool(profile.is_active and window.auto_activate)

    from app.schemas.user import UserCreateRequest

    payload = UserCreateRequest(
        username=profile.username,
        email=email,
        password=password,
        display_name=display_name,
        avatar=avatar,
    )

    try:
        try:
            user = create_user(db, payload, is_active=is_active)
        except UsernameAlreadyExistsError:
            fallback = payload.model_copy(update={"username": None})
            user = create_user(db, fallback, is_active=is_active)
        except EmailAlreadyExistsError:
            fallback_email = f"{profile.external_id}+{uuid.uuid4().hex[:6]}@linux.do"
            fallback = payload.model_copy(update={"email": fallback_email, "username": None})
            user = create_user(db, fallback, is_active=is_active)
    except Exception:
        rollback_registration_slot(db, window.id)
        raise

    try:
        get_or_create_account_for_user(db, user.id)
        assign_default_role(db, user.id)
    except Exception:
        rollback_registration_slot(db, window.id)
        raise

    return user, not window.auto_activate


def _attach_identity(db: Session, user: User, profile: LinuxDoUserProfile) -> None:
    identity = Identity(
        user_id=user.id,
        provider=LINUXDO_PROVIDER,
        external_id=profile.external_id,
        display_name=profile.username or profile.display_name,
    )
    db.add(identity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning(
            "LinuxDo identity upsert hit race condition for external_id=%s",
            profile.external_id,
        )
    finally:
        db.refresh(user)


__all__ = [
    "LinuxDoOAuthError",
    "build_linuxdo_authorize_url",
    "complete_linuxdo_oauth_flow",
]
