"""
Provider health-check helpers.

User Story 1 requires that misconfigured providers are skipped and that
we can check basic health for a given provider. This module exposes a
simple health probe based on calling the models endpoint and measuring
latency.
"""

from __future__ import annotations

import time

import httpx
from pydantic import BaseModel, Field

from app.logging_config import logger
from app.schemas import ProviderConfig, ProviderStatus
from app.provider.key_pool import (
    NoAvailableProviderKey,
    acquire_provider_key,
    record_key_failure,
    record_key_success,
)

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - fallback when redis not installed
    Redis = object  # type: ignore[misc,assignment]


class HealthStatus(BaseModel):
    """
    Minimal health status model aligned with provider-api.yaml.
    """

    provider_id: str = Field(..., description="Provider id")
    status: ProviderStatus = Field(..., description="Health status")
    timestamp: float = Field(..., description="Check timestamp (epoch seconds)")
    response_time_ms: float | None = Field(
        None, description="Response time in milliseconds"
    )
    error_message: str | None = Field(
        None, description="Error message if check failed"
    )
    last_successful_check: float | None = Field(
        None, description="Timestamp of last successful check"
    )


async def check_provider_health(
    client: httpx.AsyncClient,
    provider: ProviderConfig,
    redis: Redis | None = None,
) -> HealthStatus:
    """
    Perform a lightweight health check by calling the provider's models endpoint.
    """
    try:
        selection = await acquire_provider_key(provider, redis)
    except NoAvailableProviderKey as exc:
        return HealthStatus(
            provider_id=provider.id,
            status=ProviderStatus.DOWN,
            timestamp=time.time(),
            response_time_ms=0.0,
            error_message=str(exc),
            last_successful_check=None,
        )

    base = str(provider.base_url).rstrip("/")
    path = provider.models_path or "/v1/models"
    url = f"{base}/{path.lstrip('/')}"

    headers = {
        "Authorization": f"Bearer {selection.key}",
        "Accept": "application/json",
    }
    if provider.custom_headers:
        headers.update(provider.custom_headers)

    logger.info("Health check for provider %s at %s", provider.id, url)

    start = time.perf_counter()
    status = ProviderStatus.HEALTHY
    error_message: str | None = None
    last_success: float | None = None

    try:
        resp = await client.get(url, headers=headers)
        duration_ms = (time.perf_counter() - start) * 1000.0
        status_code = resp.status_code
        if status_code >= 500:
            status = ProviderStatus.DOWN
            error_message = f"HTTP {status_code}"
            record_key_failure(
                selection, retryable=True, status_code=status_code, redis=redis
            )
        elif status_code >= 400:
            status = ProviderStatus.DEGRADED
            error_message = f"HTTP {status_code}"
            record_key_failure(
                selection,
                retryable=status_code >= 429,
                status_code=status_code,
                redis=redis,
            )
        else:
            last_success = time.time()
            record_key_success(selection, redis=redis)
    except httpx.HTTPError as exc:
        duration_ms = (time.perf_counter() - start) * 1000.0
        status = ProviderStatus.DOWN
        error_message = str(exc)
        record_key_failure(selection, retryable=True, status_code=None, redis=redis)

    return HealthStatus(
        provider_id=provider.id,
        status=status,
        timestamp=time.time(),
        response_time_ms=duration_ms,
        error_message=error_message,
        last_successful_check=last_success,
    )


__all__ = ["HealthStatus", "check_provider_health"]
