"""
Video generation task status cache.

Provides Redis caching for video generation task status to reduce database queries
during frontend polling. Uses different TTLs based on task status:
- In-progress (queued/running): 10 seconds
- Completed (succeeded/failed): 1 hour
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.logging_config import logger
from app.redis_client import redis_delete, redis_get_json, redis_set_json

# Cache key template: video:task:{task_id}
CACHE_KEY_TEMPLATE = "video:task:{task_id}"

# TTL configuration
TTL_IN_PROGRESS = 10  # 10 seconds for queued/running tasks
TTL_COMPLETED = 3600  # 1 hour for succeeded/failed tasks


class CachedTaskStatus(BaseModel):
    """Cached video generation task status."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    progress: int | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


def _compute_ttl(status: str) -> int:
    """Compute TTL based on task status."""
    if status in ("succeeded", "failed"):
        return TTL_COMPLETED
    return TTL_IN_PROGRESS


async def get_cached_task_status(redis, task_id: str) -> CachedTaskStatus | None:
    """
    Get cached task status from Redis.

    Args:
        redis: Redis client instance
        task_id: The task ID to look up

    Returns:
        CachedTaskStatus if found and valid, None otherwise
    """
    key = CACHE_KEY_TEMPLATE.format(task_id=task_id)
    data = await redis_get_json(redis, key)
    if not data:
        return None
    try:
        return CachedTaskStatus.model_validate(data)
    except ValidationError:
        # Invalid cache entry, delete it
        await redis_delete(redis, key)
        return None


async def cache_task_status(redis, entry: CachedTaskStatus) -> None:
    """
    Cache task status to Redis.

    Args:
        redis: Redis client instance
        entry: The task status to cache
    """
    key = CACHE_KEY_TEMPLATE.format(task_id=entry.task_id)
    ttl = _compute_ttl(entry.status)
    payload = entry.model_dump(mode="json")
    await redis_set_json(redis, key, payload, ttl_seconds=ttl)


async def invalidate_task_cache(redis, task_id: str) -> None:
    """
    Invalidate (delete) cached task status.

    Args:
        redis: Redis client instance
        task_id: The task ID to invalidate
    """
    key = CACHE_KEY_TEMPLATE.format(task_id=task_id)
    await redis_delete(redis, key)


async def update_task_progress(
    redis,
    task_id: str,
    progress: int,
    status: Literal["queued", "running"] = "running",
) -> None:
    """
    Update task progress in cache (for long-running tasks).

    This is a partial update that preserves existing cache data
    while updating progress and optionally status.

    Args:
        redis: Redis client instance
        task_id: The task ID
        progress: Progress percentage (0-100)
        status: Task status (default: running)
    """
    cached = await get_cached_task_status(redis, task_id)
    if cached:
        cached.progress = progress
        cached.status = status
        await cache_task_status(redis, cached)


__all__ = [
    "CACHE_KEY_TEMPLATE",
    "CachedTaskStatus",
    "cache_task_status",
    "get_cached_task_status",
    "invalidate_task_cache",
    "update_task_progress",
]
