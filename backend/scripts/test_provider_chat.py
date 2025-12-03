#!/usr/bin/env python
"""简单的厂商聊天连通性测试脚本。"""

from __future__ import annotations

import asyncio
import json
from getpass import getpass
from typing import Any

import httpx


def _prompt(label: str, *, secret: bool = False, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    text = (
        getpass(f"{label}{suffix}: ") if secret else input(f"{label}{suffix}: ")
    ).strip()
    if not text and default is not None:
        return default
    if not text:
        raise SystemExit(f"{label} 不能为空")
    return text


def _build_payload(model: str, message: str, stream: bool) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": stream,
    }


async def _send_request(
    base_url: str, api_key: str, payload: dict[str, Any], stream: bool
) -> None:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }

    async with httpx.AsyncClient(timeout=None) as client:
        if stream:
            print(f"POST {url} (streaming) ...")
            try:
                async with client.stream(
                    "POST", url, headers=headers, json=payload
                ) as resp:
                    print(f"HTTP {resp.status_code}")
                    async for chunk in resp.aiter_text():
                        if chunk:
                            print(chunk, end="", flush=True)
                    print("\n[stream finished]")
            except httpx.HTTPError as exc:
                print(f"请求失败: {exc}")
        else:
            print(f"POST {url} ...")
            try:
                resp = await client.post(url, headers=headers, json=payload)
                print(f"HTTP {resp.status_code}")
                try:
                    parsed = resp.json()
                    print(json.dumps(parsed, ensure_ascii=False, indent=2)[:4000])
                except json.JSONDecodeError:
                    print(resp.text[:4000])
            except httpx.HTTPError as exc:
                print(f"请求失败: {exc}")


async def main() -> None:
    base_url = _prompt("Provider base URL", default="https://api.example.com")
    api_key = _prompt("Provider API key", secret=True)
    model = _prompt("Model ID")
    message = _prompt(
        "Test message", default="你好，测试对话连通性。"
    )
    stream_choice = _prompt("Enable streaming? (y/N)", default="N").lower()
    stream = stream_choice.startswith("y")

    payload = _build_payload(model=model, message=message, stream=stream)
    await _send_request(base_url=base_url, api_key=api_key, payload=payload, stream=stream)


if __name__ == "__main__":
    asyncio.run(main())
