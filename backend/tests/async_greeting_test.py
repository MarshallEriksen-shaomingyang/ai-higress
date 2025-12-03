import asyncio
import json
from typing import Any

import httpx

API_BASE_URL = "http://127.0.0.1:8000"
API_KEY = "dGltZWxpbmU="  # base64("timeline")


async def call_chat_completion(
    *, message: str, stream: bool = False
) -> dict[str, Any] | None:
    """
    使用 async + httpx.AsyncClient 方式，向网关发起一个问候请求。
    当 stream=False 时直接返回 JSON；当 stream=True 时打印流式输出。
    """
    url = f"{API_BASE_URL.rstrip('/')}/v1/chat/completions"

    payload: dict[str, Any] = {
        "model": "test-model",  # 根据你的实际可用模型修改
        "messages": [
            {"role": "user", "content": message},
        ],
        "stream": stream,
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        if not stream:
            resp = await client.post(url, json=payload, headers=headers)
            print(f"HTTP {resp.status_code}")
            try:
                data = resp.json()
            except json.JSONDecodeError:
                print("响应不是合法 JSON：", resp.text)
                return None

            print(json.dumps(data, ensure_ascii=False, indent=2))
            return data

        # 流式模式
        headers_stream = {
            **headers,
            "Accept": "text/event-stream",
        }
        async with client.stream(
            "POST", url, json=payload, headers=headers_stream
        ) as resp:
            print(f"HTTP {resp.status_code} (streaming)")
            async for line in resp.aiter_lines():
                if not line:
                    continue
                print(line)

    return None


async def main() -> None:
    # 非流式示例
    print("=== 非流式问候 ===")
    await call_chat_completion(message="你好", stream=False)

    # 流式示例（如果你的前后端和上游支持流式）
    print("\n=== 流式问候 ===")
    await call_chat_completion(message="你好（流式）", stream=True)


if __name__ == "__main__":
    asyncio.run(main())

