import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .context_store import save_context
from .logging_config import logger


def detect_request_format(payload: dict[str, Any]) -> str:
    """
    Try to detect whether the incoming payload is OpenAI-style or Claude-style.

    This is heuristic-based; you can tweak these rules to fit your real traffic.
    """
    # Claude-style uses max_tokens or max_tokens_to_sample, often with metadata keys
    if "max_tokens_to_sample" in payload:
        return "claude"
    if "anthropic_version" in payload:
        return "claude"

    # OpenAI new API also uses `max_completion_tokens`; prefer claude when clearly signaled
    if "max_completion_tokens" in payload and "anthropic_version" not in payload:
        return "openai"

    # Fallback: treat as OpenAI; both use `model` and `messages`
    return "openai"


class UpstreamStreamError(Exception):
    """
    Lightweight wrapper for upstream streaming errors that happen before
    any data has been yielded to the caller.

    When this is raised by stream_upstream, the caller is still free to
    retry the request against another provider.
    """

    def __init__(
        self,
        *,
        status_code: int | None,
        message: str,
        text: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.text = text


async def stream_upstream(
    *,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    redis,
    session_id: str | None,
) -> AsyncIterator[bytes]:
    """
    Stream data from upstream and forward chunks immediately to the caller.

    Behaviour:
    - When the upstream returns an HTTP error status *before* the stream
      starts, this function raises UpstreamStreamError so the caller can
      decide whether to retry on another provider.
    - When a transport error happens *after* at least one chunk has been
      yielded, we emit a final SSE-style error frame instead of raising,
      because the HTTP response has already started.
    - Conversation context is saved once the upstream stream finishes or
      we have emitted a terminal error frame.
    """
    logger.info(
        "stream_upstream: opening %s %s (session_id=%r)",
        method,
        url,
        session_id,
    )
    buffer = bytearray()
    try:
        async with client.stream(method, url, headers=headers, json=json_body) as resp:
            # HTTP status errors before streaming starts: let the caller
            # decide whether to retry on another provider.
            if resp.status_code >= 400:
                text_bytes = await resp.aread()
                text = text_bytes.decode("utf-8", errors="ignore")

                try:
                    payload_str = json.dumps(json_body, ensure_ascii=False)
                except TypeError:
                    payload_str = repr(json_body)

                logger.warning(
                    "Upstream streaming HTTP error %s for %s; payload=%s; response=%s",
                    resp.status_code,
                    url,
                    payload_str,
                    text,
                )

                raise UpstreamStreamError(
                    status_code=resp.status_code,
                    message=f"Upstream HTTP error {resp.status_code}",
                    text=text,
                )

            logger.info(
                "stream_upstream: connected to upstream %s with status %s",
                url,
                resp.status_code,
            )

            sent_any = False
            chunk_count = 0

            try:
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    chunk_count += 1
                    if chunk_count == 1:
                        logger.info(
                            "stream_upstream: received first chunk from %s", url
                        )
                    buffer.extend(chunk)
                    sent_any = True
                    # Stream chunk to caller
                    yield chunk
            except httpx.HTTPError as exc:
                # Transport-level error while streaming.
                logger.warning(
                    "Upstream streaming transport error for %s: %s", url, exc
                )

                if not sent_any:
                    # No data has been sent to the client yet, so the
                    # caller can still retry on another provider.
                    raise UpstreamStreamError(
                        status_code=None,
                        message="Upstream streaming transport error",
                        text=str(exc),
                    ) from exc

                # We have already yielded some data; emit a final SSE
                # error frame instead of bubbling the exception.
                payload = {
                    "error": {
                        "type": "upstream_error",
                        "status": None,
                        "message": str(exc),
                    }
                }
                error_chunk = (
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                ).encode()
                buffer.extend(error_chunk)
                yield error_chunk
    finally:
        # Save context after stream finishes (or fails)
        if buffer:
            logger.info(
                "stream_upstream: finished streaming from %s, "
                "buffer_bytes=%d; saving context",
                url,
                len(buffer),
            )
            await save_context(
                redis, session_id, json_body, buffer.decode("utf-8", errors="ignore")
            )


__all__ = ["UpstreamStreamError", "detect_request_format", "stream_upstream"]
