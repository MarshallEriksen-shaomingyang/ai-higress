#!/usr/bin/env python
"""
将明文 token 转成 Base64，方便用于 Authorization: Bearer <token> 请求头。

用法示例：
    uv run scripts/encode_token.py timeline
"""

from __future__ import annotations

import argparse
import base64
import sys


def encode_token(value: str) -> str:
    """Encode the provided string as Base64 (UTF-8)."""
    if not value:
        raise ValueError("token 不能为空")
    encoded = base64.b64encode(value.encode("utf-8"))
    return encoded.decode("ascii")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将明文 token 转为 Base64，用于 Authorization 头。",
    )
    parser.add_argument(
        "token",
        nargs="?",
        help="要编码的明文 token，例如 timeline",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    token = args.token
    if not token:
        token = input("请输入要编码的明文 token: ").strip()
    if not token:
        print("token 不能为空", file=sys.stderr)
        sys.exit(1)

    try:
        encoded = encode_token(token)
    except ValueError as exc:
        print(f"编码失败: {exc}", file=sys.stderr)
        sys.exit(1)

    print("=== 编码结果 ===")
    print(f"明文: {token}")
    print(f"Base64: {encoded}")
    print("\n在请求头中使用：")
    print(f"Authorization: Bearer {encoded}")


if __name__ == "__main__":
    main()
