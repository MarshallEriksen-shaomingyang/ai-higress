from __future__ import annotations

import base64
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db
from app.models import APIKey, Base, User
from app.services.api_key_service import (
    APIKeyExpiry,
    build_api_key_prefix,
    derive_api_key_hash,
)
from app.services.jwt_auth_service import create_access_token, hash_password


def install_inmemory_db(app, *, token_plain: str = "timeline") -> sessionmaker[Session]:
    """
    Attach an in-memory SQLite database to the FastAPI app and seed a default API key.
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with SessionLocal() as session:
        seed_user_and_key(session, token_plain=token_plain)

    def _cleanup() -> None:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    app.add_event_handler("shutdown", _cleanup)

    return SessionLocal


def seed_user_and_key(
    session: Session,
    *,
    token_plain: str,
    username: str = "admin",
    email: str = "admin@example.com",
    is_superuser: bool = True,
) -> tuple[User, APIKey]:
    def _hash_password_safe(raw: str) -> str:
        """
        测试环境缺少 bcrypt 后端时退化为直接写入明文。
        """
        try:
            return hash_password(raw)
        except ValueError:
            # 驱动检测在CI容器里可能失败，直接退回到明文方便种子数据写入。
            return raw

    user = User(
        username=username,
        email=email,
        hashed_password=_hash_password_safe("Secret123!"),
        is_active=True,
        is_superuser=is_superuser,
    )
    session.add(user)
    session.flush()

    api_key = APIKey(
        user_id=user.id,
        name=f"{username}-key",
        key_hash=derive_api_key_hash(token_plain),
        key_prefix=build_api_key_prefix(token_plain),
        expiry_type=APIKeyExpiry.NEVER.value,
        expires_at=None,
        is_active=True,
        disabled_reason=None,
    )
    session.add(api_key)
    session.commit()
    session.refresh(user)
    session.refresh(api_key)
    session.expunge(user)
    session.expunge(api_key)

    return user, api_key


def auth_headers(token_plain: str = "timeline") -> dict[str, str]:
    """生成 API Key 格式的认证头（用于模型访问路由）"""
    encoded = base64.b64encode(token_plain.encode("utf-8")).decode("ascii")
    return {"Authorization": f"Bearer {encoded}"}


def jwt_auth_headers(user_id: str) -> dict[str, str]:
    """生成 JWT token 格式的认证头（用于用户管理路由）"""
    access_token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {access_token}"}


class InMemoryRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value

    async def delete(self, key: str):
        self._data.pop(key, None)


__all__ = ["InMemoryRedis", "auth_headers", "jwt_auth_headers", "install_inmemory_db", "seed_user_and_key"]
