#!/usr/bin/env python
"""
实用脚本：查询 Redis 中的模型缓存并调用 API 做快速回归验证。

主要功能：
1. 列出 llm:vendor:*:models 缓存的存在情况与条目数量；
2. 调用 /models 接口确认逻辑模型汇总；
3. 可选地向 /v1/chat/completions 发送一条测试请求，验证指定模型是否可用。
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from typing import Any

import httpx

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - 适配无 redis 环境
    Redis = None  # type: ignore[assignment]

from app.settings import settings


def _build_auth_header(token_plain: str) -> str:
    encoded = base64.b64encode(token_plain.encode("utf-8")).decode("ascii")
    return f"Bearer {encoded}"


async def inspect_redis_models(redis_url: str) -> list[str]:
    if Redis is None:
        print("redis 库不可用，跳过 Redis 检查。")
        return []

    redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        keys: list[str] = await redis.keys("llm:vendor:*:models")
        if not keys:
            print("Redis 中未找到 llm:vendor:*:models 缓存。")
            return []

        print(f"Redis 中共有 {len(keys)} 个 llm:vendor:*:models 缓存：")
        for key in sorted(keys):
            raw = await redis.get(key)
            try:
                data = json.loads(raw) if raw else []
            except json.JSONDecodeError:
                data = []
            print(f"  - {key}: {len(data)} 条记录")
        return keys
    finally:
        await redis.close()


async def call_models(api_base: str, auth_header: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={"Authorization": auth_header})
    print(f"GET {url} -> {resp.status_code}")
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        print("  返回内容不是 JSON：")
        print(resp.text[:500])
        return {}

    total = len(payload.get("data", [])) if isinstance(payload, dict) else 0
    print(f"  /models 返回 {total} 个模型。")
    return payload


async def call_chat_completion(
    api_base: str,
    auth_header: str,
    model: str,
    message: str,
) -> None:
    url = f"{api_base.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)

    print(f"POST {url} -> {resp.status_code}")
    print(resp.text[:800])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查 Redis 模型缓存并调用 API 做回归测试。",
    )
    parser.add_argument(
        "--redis-url",
        default=settings.redis_url,
        help=f"Redis 连接字符串（默认 {settings.redis_url!r}）",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="API 基础地址，默认 http://localhost:8000",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.1",
        help="回归测试使用的模型名称，默认 gpt-5.1",
    )
    parser.add_argument(
        "--message",
        default="你好，做一次模型连通性回归。",
        help="发送到聊天接口的测试内容。",
    )
    parser.add_argument(
        "--auth-token",
        required=True,
        help="用户 API 密钥明文，脚本会自动 base64 编码 Authorization 头。",
    )
    parser.add_argument(
        "--skip-chat",
        action="store_true",
        help="只检查 Redis 与 /models，不调用 /v1/chat/completions。",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    auth_header = _build_auth_header(args.auth_token)

    print("=== Redis 模型缓存检查 ===")
    await inspect_redis_models(args.redis_url)

    print("\n=== /models 接口检查 ===")
    await call_models(args.api_base, auth_header)

    if not args.skip_chat:
        print("\n=== /v1/chat/completions 回归测试 ===")
        await call_chat_completion(
            api_base=args.api_base,
            auth_header=auth_header,
            model=args.model,
            message=args.message,
        )


if __name__ == "__main__":
    asyncio.run(main())
