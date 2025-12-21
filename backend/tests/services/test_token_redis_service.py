from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.token import DeviceInfo
from app.services.token_redis_service import (
    REFRESH_TOKEN_KEY,
    TokenRedisService,
)
from tests.utils import InMemoryRedis


@pytest.mark.asyncio
async def test_cleanup_user_sessions_removes_invalid_and_damaged_entries():
    redis = InMemoryRedis()
    service = TokenRedisService(redis)

    user_id = "user-1"

    # 创建两个有效的 refresh token，会自动写入会话索引
    expires_in = 3600
    device_info = DeviceInfo(user_agent="pytest", ip_address="127.0.0.1")

    await service.store_refresh_token(
        token_id="t-valid-1",
        user_id=user_id,
        jti="j-valid-1",
        family_id="family-1",
        expires_in=expires_in,
        device_info=device_info,
    )
    await service.store_refresh_token(
        token_id="t-valid-2",
        user_id=user_id,
        jti="j-valid-2",
        family_id="family-1",
        expires_in=expires_in,
        device_info=device_info,
    )

    # 手动向 sessions 列表中插入一条「损坏」记录
    sessions_key = f"auth:user:{user_id}:sessions"
    raw = await redis.get(sessions_key)
    assert raw is not None

    import json

    data = json.loads(raw)
    # 追加一个缺失必要字段的对象，模拟损坏会话
    data["sessions"].append({"invalid": True})
    await redis.set(sessions_key, json.dumps(data))

    # 删除其中一个 refresh token，模拟已过期/丢失的 token
    await redis.delete(REFRESH_TOKEN_KEY.format(token_id="t-valid-1"))

    removed = await service.cleanup_user_sessions(user_id)
    # 期望至少移除：1 条损坏记录 + 1 条失效 token 对应的会话
    assert removed >= 2

    # 剩余会话中应只包含仍然有效的 refresh token 对应会话
    cleaned_sessions = await service.get_user_sessions(user_id)
    assert len(cleaned_sessions) == 1
    assert cleaned_sessions[0].session_id == "t-valid-2"


@pytest.mark.asyncio
async def test_enforce_session_limit_evicts_oldest_sessions(monkeypatch):
    redis = InMemoryRedis()
    service = TokenRedisService(redis)
    user_id = "user-2"

    expires_in = 3600

    # 创建 3 个会话，并人为设置 last_used_at 以区分新旧
    now = datetime.now(UTC)

    async def _add_session(token_id: str, jti: str, offset_seconds: int):
        await service.store_refresh_token(
            token_id=token_id,
            user_id=user_id,
            jti=jti,
            family_id="family-2",
            expires_in=expires_in,
            device_info=None,
        )
        # 覆写 last_used_at
        sessions_key = f"auth:user:{user_id}:sessions"
        import json

        raw = await redis.get(sessions_key)
        data = json.loads(raw)
        for sess in data["sessions"]:
            if sess.get("session_id") == token_id:
                sess["last_used_at"] = (now + timedelta(seconds=offset_seconds)).isoformat()
        await redis.set(sessions_key, json.dumps(data))

    await _add_session("t-oldest", "j-oldest", 0)
    await _add_session("t-middle", "j-middle", 10)
    await _add_session("t-newest", "j-newest", 20)

    # 限制为最多 2 个会话，应淘汰最旧的 t-oldest
    revoked = await service.enforce_session_limit(user_id, max_sessions=2)
    assert revoked == 1

    remaining_sessions = await service.get_user_sessions(user_id)
    remaining_ids = {s.session_id for s in remaining_sessions}
    assert remaining_ids == {"t-middle", "t-newest"}

