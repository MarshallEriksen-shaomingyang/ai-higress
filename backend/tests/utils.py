from __future__ import annotations

import fnmatch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.deps import get_db, get_redis
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
    app.dependency_overrides[get_db_session] = override_get_db

    redis = InMemoryRedis()
    app.state._test_redis = redis

    async def override_get_redis():
        return redis

    app.dependency_overrides[get_redis] = override_get_redis

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
    return {"Authorization": f"Bearer {token_plain}"}


def jwt_auth_headers(user_id: str) -> dict[str, str]:
    """生成 JWT token 格式的认证头（用于用户管理路由）"""
    access_token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {access_token}"}


class InMemoryRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}
        self._counters: dict[str, int] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._lists: dict[str, list[str]] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value

    async def incr(self, key: str) -> int:
        current = int(self._counters.get(key, 0))
        current += 1
        self._counters[key] = current
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Minimal TTL stub.
        Tests generally do not depend on key expiry; return True for compatibility.
        """
        _ = (key, seconds)
        return True

    async def zadd(self, key: str, mapping: dict[str, float], nx: bool = False) -> int:
        z = self._zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if nx and member in z:
                continue
            z[member] = float(score)
            added += 1
        return added

    async def zscore(self, key: str, member: str):
        z = self._zsets.get(key, {})
        val = z.get(member)
        if val is None:
            return None
        return float(val)

    async def zincrby(self, key: str, amount: float, member: str) -> float:
        z = self._zsets.setdefault(key, {})
        z[member] = float(z.get(member, 0.0)) + float(amount)
        return float(z[member])

    async def exists(self, *keys: str) -> int:
        """返回存在的 key 数量，模拟 Redis exists 行为。"""
        return sum(1 for key in keys if key in self._data)

    async def keys(self, pattern: str):
        """使用 fnmatch 实现简单模式匹配。"""
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._data:
                removed += 1
                self._data.pop(key, None)
            if key in self._sets:
                removed += 1
                self._sets.pop(key, None)
            if key in self._lists:
                removed += 1
                self._lists.pop(key, None)
        return removed

    # --- Set operations (minimal subset used by proxy pool) ---

    async def sadd(self, key: str, *members: str) -> int:
        s = self._sets.setdefault(key, set())
        before = len(s)
        s.update(members)
        return len(s) - before

    async def srem(self, key: str, *members: str) -> int:
        s = self._sets.get(key, set())
        before = len(s)
        for m in members:
            s.discard(m)
        self._sets[key] = s
        return before - len(s)

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    async def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))

    async def srandmember(self, key: str):
        import random

        s = list(self._sets.get(key, set()))
        if not s:
            return None
        return random.choice(s)

    # --- List operations (minimal subset used by context store) ---

    async def lpush(self, key: str, value: str) -> int:
        lst = self._lists.setdefault(key, [])
        lst.insert(0, str(value))
        return len(lst)

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        """
        Keep only elements within [start, stop] (inclusive), supports negative indices.
        """
        lst = self._lists.get(key, [])
        if not lst:
            self._lists[key] = []
            return True

        n = len(lst)
        s = int(start)
        e = int(stop)
        if s < 0:
            s = n + s
        if e < 0:
            e = n + e
        if s < 0:
            s = 0
        if e < 0:
            self._lists[key] = []
            return True
        if s >= n:
            self._lists[key] = []
            return True
        if e >= n:
            e = n - 1
        if e < s:
            self._lists[key] = []
            return True

        self._lists[key] = lst[s : e + 1]
        return True

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        lst = self._lists.get(key, [])
        if not lst:
            return []

        n = len(lst)
        s = int(start)
        e = int(stop)
        if s < 0:
            s = n + s
        if e < 0:
            e = n + e
        if s < 0:
            s = 0
        if s >= n:
            return []
        if e >= n:
            e = n - 1
        if e < s:
            return []
        return list(lst[s : e + 1])


__all__ = ["InMemoryRedis", "auth_headers", "install_inmemory_db", "jwt_auth_headers", "seed_user_and_key"]
