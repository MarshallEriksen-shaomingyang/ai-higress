#!/usr/bin/env python
"""
实用脚本：测试上游代理池的有效性与连通性。

支持：
- 从 .env 的 UPSTREAM_PROXY_POOL 读取代理列表（默认）；
- 通过 --proxies 或 --file 传入代理列表；
- 并发测试、统计延迟、输出可用代理列表。

示例：
  python backend/scripts/check_proxies.py
  python backend/scripts/check_proxies.py --url https://httpbin.org/ip
  python backend/scripts/check_proxies.py --proxies "http://1.2.3.4:8080, socks5://5.6.7.8:1080"
  python backend/scripts/check_proxies.py --file proxies.txt --concurrency 20
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# 允许从仓库根目录直接运行：python backend/scripts/check_proxies.py
_backend_root = Path(__file__).resolve().parents[1]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.proxy_pool import _parse_proxy_pool  # noqa: E402
from app.settings import settings  # noqa: E402


@dataclass
class ProxyCheckResult:
    proxy: str
    ok: bool
    status_code: int | None
    latency_ms: float | None
    ip: str | None
    error: str | None


def _ensure_socks_support(proxies: list[str]) -> None:
    """
    httpx 的 SOCKS 代理依赖 socksio；未安装时会在运行期报错。
    这里提前给出更友好的提示。
    """
    if not proxies:
        return
    if not any(p.lower().startswith(("socks5://", "socks5h://")) for p in proxies):
        return
    try:
        import socksio  # noqa: F401
    except ModuleNotFoundError:
        raise SystemExit(
            "检测到 SOCKS 代理，但当前环境未安装 socksio。\n"
            "请在 backend 虚拟环境中安装：\n"
            "  pip install socksio\n"
            "或：\n"
            "  pip install \"httpx[socks]\"\n"
            "\n"
            "不想装依赖也可以用 curl 直接测：\n"
            "  curl --proxy socks5h://HOST:PORT https://api.ipify.org?format=json\n"
        )


def _load_proxies_from_file(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"代理文件不存在: {path}")
    raw_lines = p.read_text(encoding="utf-8").splitlines()
    items: list[str] = []
    for line in raw_lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        items.append(s)
    # 复用同一解析/过滤规则
    return _parse_proxy_pool(",".join(items))


def _unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试代理池有效性")
    parser.add_argument(
        "--proxies",
        default="",
        help="代理列表字符串（逗号/换行分隔）。不填则从 UPSTREAM_PROXY_POOL 读取。",
    )
    parser.add_argument(
        "--file",
        default="",
        help="包含代理的文件路径（每行一个，可含 # 注释）。",
    )
    parser.add_argument(
        "--url",
        default="https://api.ipify.org?format=json",
        help="用于测试的目标 URL（默认 https://api.ipify.org?format=json）。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="每次请求超时（秒）。默认 8 秒。",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="每个代理的重试次数（失败时再次尝试）。默认 1 次（不额外重试）。",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="并发检测数。默认 10。",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印失败的详细异常信息。",
    )
    return parser.parse_args()


async def _check_one(
    proxy: str,
    *,
    url: str,
    timeout: float,
    retries: int,
) -> ProxyCheckResult:
    last_error: str | None = None
    for attempt in range(max(retries, 1)):
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
                resp = await client.get(url)
            latency_ms = (time.perf_counter() - start) * 1000.0
            ip = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                try:
                    payload: Any = resp.json()
                    if isinstance(payload, dict):
                        ip = payload.get("ip") or payload.get("origin")
                except json.JSONDecodeError:
                    pass
            ok = resp.status_code < 400
            if ok:
                return ProxyCheckResult(
                    proxy=proxy,
                    ok=True,
                    status_code=resp.status_code,
                    latency_ms=latency_ms,
                    ip=ip,
                    error=None,
                )
            last_error = f"HTTP {resp.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        except Exception as exc:  # pragma: no cover - 防御性兜底
            last_error = repr(exc)

    return ProxyCheckResult(
        proxy=proxy,
        ok=False,
        status_code=None,
        latency_ms=None,
        ip=None,
        error=last_error,
    )


async def main() -> None:
    args = parse_args()

    proxies: list[str] = []
    if args.file:
        proxies.extend(_load_proxies_from_file(args.file))
    if args.proxies:
        proxies.extend(_parse_proxy_pool(args.proxies))
    if not proxies:
        proxies = _parse_proxy_pool(settings.upstream_proxy_pool)

    proxies = _unique_keep_order(proxies)
    _ensure_socks_support(proxies)

    if not proxies:
        print("未找到任何代理，请检查 UPSTREAM_PROXY_POOL / --proxies / --file。")
        return

    print(f"将测试 {len(proxies)} 个代理，目标 URL: {args.url}")

    sem = asyncio.Semaphore(max(1, args.concurrency))

    async def _run(proxy: str) -> ProxyCheckResult:
        async with sem:
            return await _check_one(
                proxy,
                url=args.url,
                timeout=args.timeout,
                retries=args.retries,
            )

    tasks = [asyncio.create_task(_run(p)) for p in proxies]
    results = await asyncio.gather(*tasks)

    ok_list = [r for r in results if r.ok]
    bad_list = [r for r in results if not r.ok]

    print("\n=== 可用代理 ===")
    for r in ok_list:
        extra = f" ip={r.ip}" if r.ip else ""
        print(f"[OK] {r.proxy}  latency={r.latency_ms:.0f}ms{extra}")

    print("\n=== 不可用代理 ===")
    for r in bad_list:
        if args.verbose and r.error:
            print(f"[FAIL] {r.proxy}  error={r.error}")
        else:
            msg = r.error or "unknown error"
            print(f"[FAIL] {r.proxy}  {msg}")

    print("\n=== 汇总 ===")
    print(f"可用 {len(ok_list)} / {len(results)}")
    if ok_list:
        pool_str = ", ".join(r.proxy for r in ok_list)
        print("可直接写回 .env 的 UPSTREAM_PROXY_POOL：")
        print(pool_str)


if __name__ == "__main__":
    asyncio.run(main())
