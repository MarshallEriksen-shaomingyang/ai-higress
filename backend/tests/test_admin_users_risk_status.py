from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from app.models import User
from app.services.user_risk_service import RISK_LEVEL_HIGH, evaluate_user_risk_window
from tests.utils import InMemoryRedis, jwt_auth_headers


def test_admin_users_includes_risk_fields(client, db_session):
    admin = db_session.execute(select(User).where(User.email == "admin@example.com")).scalar_one()
    admin.risk_level = "high"
    admin.risk_score = 90
    admin.risk_remark = "多 IP 且频率均匀（疑似脚本/共享）"
    admin.risk_updated_at = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    db_session.add(admin)
    db_session.commit()

    resp = client.get("/admin/users", headers=jwt_auth_headers(str(admin.id)))
    assert resp.status_code == 200

    rows = resp.json()
    assert isinstance(rows, list)
    assert rows

    row = next(item for item in rows if item["id"] == str(admin.id))
    assert row["risk_level"] == "high"
    assert row["risk_score"] == 90
    assert row["risk_remark"] == "多 IP 且频率均匀（疑似脚本/共享）"
    assert row["risk_updated_at"] is not None


@pytest.mark.asyncio
async def test_evaluate_user_risk_window_detects_uniform_multi_ip():
    redis = InMemoryRedis()
    user_id = "u1"
    now = dt.datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    bucket = now.strftime("%Y%m%d%H")

    ip_key = f"risk:user:{user_id}:ips:{bucket}"
    req_key = f"risk:user:{user_id}:req:{bucket}"

    await redis.zincrby(ip_key, 100, "ip-a")
    await redis.zincrby(ip_key, 100, "ip-b")
    await redis.zincrby(ip_key, 100, "ip-c")
    await redis.set(req_key, "300")

    status = await evaluate_user_risk_window(redis, user_id=user_id, now=now, window_hours=1)
    assert status.level == RISK_LEVEL_HIGH
    assert status.score >= 80

