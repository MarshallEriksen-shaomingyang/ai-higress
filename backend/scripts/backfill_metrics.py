from __future__ import annotations

import argparse
import datetime as dt

from app.db import SessionLocal
from app.metrics import OfflineMetricsRecalculator
from app.settings import settings


def _parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill offline aggregate metrics")
    parser.add_argument("--start", required=True, help="起始时间（ISO8601，例如 2025-02-08T00:00:00Z）")
    parser.add_argument("--end", required=True, help="结束时间（ISO8601，例如 2025-02-08T06:00:00Z）")
    parser.add_argument("--window", type=int, default=300, help="聚合窗口（秒），默认 300=5 分钟")
    parser.add_argument("--transport", type=str, default=None, help="可选过滤：传输层 http/sdk")
    parser.add_argument("--stream", action="store_true", help="仅重算流式请求")
    parser.add_argument(
        "--non-stream", action="store_true", help="仅重算非流式请求（与 --stream 互斥）"
    )

    args = parser.parse_args()

    start = _parse_time(args.start)
    end = _parse_time(args.end)
    is_stream: bool | None = None
    if args.stream and args.non_stream:
        raise SystemExit("--stream 与 --non-stream 不能同时使用")
    if args.stream:
        is_stream = True
    if args.non_stream:
        is_stream = False

    recalculator = OfflineMetricsRecalculator(
        diff_threshold=settings.offline_metrics_diff_threshold,
        source_version=settings.offline_metrics_source_version,
        min_total_requests=settings.offline_metrics_min_total_requests,
    )

    session = SessionLocal()
    try:
        written = recalculator.recalculate_and_persist(
            session,
            start=start,
            end=end,
            window_seconds=args.window,
            transport=args.transport,
            is_stream=is_stream,
        )
        session.commit()
        print(f"Recalculated {written} aggregate buckets for window={args.window}s")
    finally:
        session.close()


if __name__ == "__main__":
    main()
