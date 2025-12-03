from collections.abc import AsyncIterator, Iterator

import httpx
from sqlalchemy.orm import Session

try:
    # Prefer the real Redis type when the dependency is installed.
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - safety fallback for minimal envs
    Redis = object  # type: ignore[misc,assignment]

from .db import get_db_session
from .redis_client import get_redis_client
from .settings import settings


async def get_redis() -> Redis:
    """
    FastAPI dependency that provides a shared Redis client.

    It delegates to app.redis_client.get_redis_client() so that the
    routing layer and other components can share the same underlying
    connection pool.

    In test environments without the `redis` package installed, tests
    are expected to override this dependency with a fake implementation.
    """
    return get_redis_client()


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """
    Short-lived AsyncClient for upstream HTTP calls.
    """
    async with httpx.AsyncClient(timeout=settings.upstream_timeout) as client:
        yield client


def get_db() -> Iterator[Session]:
    """
    Provide a synchronous SQLAlchemy session.
    """
    yield from get_db_session()
