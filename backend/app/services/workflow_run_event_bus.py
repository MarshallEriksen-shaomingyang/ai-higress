from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any
from uuid import UUID

from fastapi import Request

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore


def workflow_run_event_channel(*, run_id: UUID | str) -> str:
    return f"workflow_run_events:{run_id}"


def build_workflow_run_event_envelope(
    *,
    run_id: UUID | str,
    seq: int,
    event_type: str,
    created_at_iso: str | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    # 复用既有 run.event envelope（前端可直接复用 store）
    return {
        "type": "run.event",
        "run_id": str(run_id),
        "seq": int(seq),
        "event_type": str(event_type or "").strip() or "event",
        "created_at": created_at_iso,
        "payload": payload or {},
    }


async def publish_workflow_run_event(
    redis: Redis,
    *,
    run_id: UUID | str,
    envelope: dict[str, Any],
) -> None:
    if redis is None:
        return
    channel = workflow_run_event_channel(run_id=run_id)
    await redis.publish(channel, json.dumps(envelope, ensure_ascii=False))


def publish_workflow_run_event_best_effort(
    redis: Redis | None,
    *,
    run_id: UUID | str,
    envelope: dict[str, Any],
) -> None:
    if redis is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(publish_workflow_run_event(redis, run_id=run_id, envelope=envelope))


def _decode_pubsub_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = value.decode("utf-8", errors="ignore")
    elif isinstance(value, str):
        raw = value
    else:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def subscribe_workflow_run_events(
    redis: Redis,
    *,
    run_id: UUID | str,
    after_seq: int,
    request: Request | None = None,
    heartbeat_seconds: int = 15,
) -> AsyncIterator[dict[str, Any]]:
    """
    订阅 WorkflowRunEvent 的 Redis 热通道（pub/sub）。
    """
    channel = workflow_run_event_channel(run_id=run_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    last_activity = time.monotonic()
    current_after = int(after_seq or 0)

    try:
        while True:
            if request is not None:
                try:
                    if await request.is_disconnected():
                        break
                except Exception:  # pragma: no cover
                    break

            msg = None
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except Exception:
                msg = None

            if isinstance(msg, dict) and msg.get("type") == "message":
                env = _decode_pubsub_payload(msg.get("data"))
                if env is not None:
                    seq_val = env.get("seq")
                    try:
                        seq_int = int(seq_val)
                    except Exception:
                        seq_int = None
                    if seq_int is not None and seq_int > current_after:
                        current_after = seq_int
                        last_activity = time.monotonic()
                        yield env
                continue

            if time.monotonic() - last_activity >= float(heartbeat_seconds or 15):
                last_activity = time.monotonic()
                yield {
                    "type": "heartbeat",
                    "ts": int(time.time()),
                    "run_id": str(run_id),
                    "after_seq": current_after,
                }
    finally:
        with suppress(Exception):
            await pubsub.unsubscribe(channel)
        with suppress(Exception):
            await pubsub.close()


__all__ = [
    "build_workflow_run_event_envelope",
    "publish_workflow_run_event",
    "publish_workflow_run_event_best_effort",
    "subscribe_workflow_run_events",
    "workflow_run_event_channel",
]

