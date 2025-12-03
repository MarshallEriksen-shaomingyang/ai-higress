from typing import Any

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - type placeholder when redis is missing
    Redis = object  # type: ignore[misc,assignment]


async def save_context(
    redis: Redis,
    session_id: str | None,
    payload: dict[str, Any],
    response_text: str,
) -> None:
    """
    Persist conversation context into Redis.
    """
    if not session_id:
        return
    key = f"session:{session_id}:history"
    entry = {
        "request": payload,
        "response": response_text,
    }
    # Keep last 50 turns by trimming the list
    await redis.lpush(key, str(entry))
    await redis.ltrim(key, 0, 49)
