from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.deps import get_redis
from app.routes import create_app
from tests.utils import InMemoryRedis, install_inmemory_db, jwt_auth_headers, seed_user_and_key


def _setup_app_with_redis() -> tuple[TestClient, InMemoryRedis, str, str]:
  app = create_app()
  SessionLocal = install_inmemory_db(app)

  # 创建一个管理员用户和一个普通用户
  with SessionLocal() as session:
      admin, _ = seed_user_and_key(
          session,
          token_plain="admin-token",
          username="admin-user",
          email="admin-cache@example.com",
          is_superuser=True,
      )
      normal, _ = seed_user_and_key(
          session,
          token_plain="user-token",
          username="normal-user",
          email="normal-cache@example.com",
          is_superuser=False,
      )
      admin_id = str(admin.id)
      normal_id = str(normal.id)

  fake_redis = InMemoryRedis()

  async def override_get_redis():
      return fake_redis

  app.dependency_overrides[get_redis] = override_get_redis

  client = TestClient(app, base_url="http://testserver")
  return client, fake_redis, admin_id, normal_id


def test_clear_cache_requires_superuser():
  client, _, admin_id, normal_id = _setup_app_with_redis()

  # 普通用户调用应返回 403
  resp = client.post(
      "/system/cache/clear",
      headers=jwt_auth_headers(normal_id),
      json={"segments": []},
  )
  assert resp.status_code == 403

  # 超级管理员可以调用
  resp_admin = client.post(
      "/system/cache/clear",
      headers=jwt_auth_headers(admin_id),
      json={"segments": []},
  )
  assert resp_admin.status_code == 200


def test_clear_cache_removes_expected_keys():
  client, fake_redis, admin_id, _ = _setup_app_with_redis()

  # 预先写入一些缓存键
  asyncio.run(
      fake_redis.set("gateway:models:all", "payload")
  )
  asyncio.run(
      fake_redis.set("metrics:overview:summary:today:http:all", "metrics-summary")
  )
  asyncio.run(
      fake_redis.set("llm:vendor:openai:models", "models")
  )
  asyncio.run(
      fake_redis.set("llm:logical:gpt-4", "logical")
  )
  asyncio.run(
      fake_redis.set("llm:metrics:gpt-4:openai", "metrics")
  )
  asyncio.run(
      fake_redis.set("llm:metrics:history:gpt-4:openai:2024-01-01T00:00", "history")
  )

  # 只清理部分分组：例如 models + metrics_overview
  resp = client.post(
      "/system/cache/clear",
      headers=jwt_auth_headers(admin_id),
      json={"segments": ["models", "metrics_overview"]},
  )

  assert resp.status_code == 200
  body = resp.json()
  # 至少应该删除 gateway:models:all 和 metrics:overview:* 这两个前缀相关的键
  assert body["cleared_keys"] >= 2
  # 这些键应不存在
  assert asyncio.run(fake_redis.get("gateway:models:all")) is None
  assert (
      asyncio.run(fake_redis.get("metrics:overview:summary:today:http:all")) is None
  )
  # 未选择的分组不应被删除
  assert asyncio.run(fake_redis.get("llm:vendor:openai:models")) is not None
  assert asyncio.run(fake_redis.get("llm:logical:gpt-4")) is not None
  assert asyncio.run(fake_redis.get("llm:metrics:gpt-4:openai")) is not None
  assert (
      asyncio.run(
          fake_redis.get("llm:metrics:history:gpt-4:openai:2024-01-01T00:00")
      )
      is not None
  )

