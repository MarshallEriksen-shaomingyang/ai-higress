#!/usr/bin/env python
"""
Simple helper script:
- 人性化交互：给用户选项再提示输入 URL
- 也支持直接通过命令行传 URL（方便 `uv run -c` 调用）
- 默认在基础 URL 后拼接 `/models` 发送 GET 请求
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx


def build_models_url(base_url: str) -> str:
    """Normalize base URL and append '/models'."""
    base = base_url.strip().rstrip("/")
    if not base:
        raise ValueError("Base URL must not be empty")
    return f"{base}/models"


def request_and_print(full_url: str) -> None:
    """Send GET request and print JSON or text."""
    print(f"即将请求: {full_url}")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(full_url)
    except Exception as exc:
        print(f"请求失败: {exc}")
        sys.exit(1)

    print(f"HTTP 状态码: {resp.status_code}")

    # 尝试解析 JSON，否则直接打印文本
    try:
        data = resp.json()
    except Exception:
        print("返回内容（非 JSON）：")
        print(resp.text)
        return

    print("返回 JSON：")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    """Parse CLI flags so uv/命令行可以直接传 URL。"""
    parser = argparse.ArgumentParser(
        description="根据厂商 URL 请求其 /models 接口，并打印结果。",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="API 厂商基础 URL，例如 https://api.xxx.com（将自动拼接 /models）",
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="url_flag",
        help="同上，使用 flag 形式传入基础 URL（将自动拼接 /models）。",
    )
    parser.add_argument(
        "--full-url",
        help="完整请求 URL（已包含 /models 或其它路径），不会再自动拼接。",
    )
    return parser.parse_args()


def choose_url_interactively() -> str:
    """交互模式：先让用户选，再提示输入 URL。"""
    print("请选择操作方式：")
    print("1) 输入 API 厂商基础 URL，脚本自动拼接 /models")
    print("2) 输入完整请求 URL（已经包含 /models 或其它路径）")
    print("3) 退出")

    choice = input("请输入选项编号 (默认 1): ").strip() or "1"

    if choice == "3":
        print("已取消操作。")
        sys.exit(0)

    if choice == "2":
        full_url = input("请输入完整请求 URL: ").strip()
        if not full_url:
            print("URL 不能为空。")
            sys.exit(1)
        return full_url

    # 默认选项 1：基础 URL 自动拼接 /models
    base = input("请输入 API 厂商的基础 URL (例如 https://api.xxx.com): ").strip()
    try:
        return build_models_url(base)
    except ValueError as exc:
        print(f"URL 错误: {exc}")
        sys.exit(1)


def main() -> None:
    args = parse_args()

    # 优先使用 --full-url，如果提供了就完全按用户给的请求
    if args.full_url:
        full_url = args.full_url.strip()
    # 其次：使用 flag 形式的基础 URL
    elif args.url_flag:
        full_url = build_models_url(args.url_flag)
    # 再次：使用位置参数形式的基础 URL（方便 `uv run scripts/list_models.py https://api.xxx.com`）
    elif args.url:
        full_url = build_models_url(args.url)
    # 特殊情况：有些 `uv run -c` 写法可能把 URL 当成第一个参数传进来，做个简单检测
    elif len(sys.argv) >= 2 and sys.argv[1].startswith(("http://", "https://")):
        full_url = build_models_url(sys.argv[1])
    else:
        # 完全没传 URL，就走交互式菜单，更人性化
        full_url = choose_url_interactively()

    request_and_print(full_url)


if __name__ == "__main__":
    main()
