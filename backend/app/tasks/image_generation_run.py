from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote, urlparse
from uuid import UUID

import httpx
from celery import shared_task
from sqlalchemy import select

from app.auth import AuthenticatedAPIKey
from app.db.session import SessionLocal
from app.logging_config import logger
from app.models import APIKey, Conversation, Message, Run, User
from app.redis_client import get_redis_client
from app.repositories.chat_repository import persist_run
from app.repositories.run_event_repository import append_run_event
from app.schemas.image import ImageGenerationRequest
from app.services.chat_history_service import finalize_assistant_image_generation_after_user_sequence
from app.services.image_app_service import ImageAppService
from app.services.run_event_bus import build_run_event_envelope, publish_run_event_best_effort

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


def _to_authenticated_api_key(db, *, api_key: APIKey) -> AuthenticatedAPIKey:
    user = db.execute(select(User).where(User.id == api_key.user_id)).scalars().first()
    if user is None:
        raise RuntimeError("api_key user not found")
    return AuthenticatedAPIKey(
        id=UUID(str(api_key.id)),
        user_id=UUID(str(user.id)),
        user_username=user.username,
        is_superuser=bool(user.is_superuser),
        name=api_key.name,
        is_active=bool(api_key.is_active),
        disabled_reason=api_key.disabled_reason,
        has_provider_restrictions=bool(api_key.has_provider_restrictions),
        allowed_provider_ids=list(api_key.allowed_provider_ids),
    )


def _run_to_summary(run: Run) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "requested_logical_model": run.requested_logical_model,
        "status": run.status,
        "output_preview": run.output_preview,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
        "tool_invocations": getattr(run, "tool_invocations", None),
    }


def _append_run_event_and_publish_best_effort(
    db,
    *,
    redis: Redis | None,
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> int | None:
    try:
        row = append_run_event(db, run_id=run_id, event_type=event_type, payload=payload)
        created_at_iso = None
        try:
            created_at_iso = row.created_at.isoformat() if getattr(row, "created_at", None) is not None else None
        except Exception:
            created_at_iso = None
        publish_run_event_best_effort(
            redis,
            run_id=run_id,
            envelope=build_run_event_envelope(
                run_id=run_id,
                seq=int(getattr(row, "seq", 0) or 0),
                event_type=str(getattr(row, "event_type", event_type) or event_type),
                created_at_iso=created_at_iso,
                payload=payload,
            ),
        )
        return int(getattr(row, "seq", 0) or 0)
    except Exception:  # pragma: no cover
        logger.debug(
            "image_generation task: append_run_event failed (run_id=%s type=%s)",
            run_id,
            event_type,
            exc_info=True,
        )
        return None


def _extract_object_key_from_media_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    marker = "/media/images/"
    if marker not in parsed.path:
        return None
    return unquote(parsed.path.split(marker, 1)[1])


async def execute_image_generation_run(
    *,
    run_id: str,
    assistant_message_id: str | None = None,
    streaming: bool = False,
) -> str:
    run_uuid = UUID(str(run_id))
    SessionFactory = SessionLocal

    redis = get_redis_client()

    with SessionFactory() as db:
        run = db.get(Run, run_uuid)
        if run is None:
            return "skipped:no_run"

        if str(run.status or "") in {"succeeded", "failed", "canceled"}:
            return "skipped:already_finished"

        message = db.get(Message, UUID(str(run.message_id)))
        if message is None:
            return "failed:no_message"

        conv = db.get(Conversation, UUID(str(message.conversation_id)))
        if conv is None:
            return "failed:no_conversation"

        api_key = db.get(APIKey, UUID(str(run.api_key_id)))
        if api_key is None:
            return "failed:no_api_key"

        auth_key = _to_authenticated_api_key(db, api_key=api_key)

        prompt = ""
        request_payload: dict[str, Any] = {}
        if isinstance(run.request_payload, dict):
            request_payload = dict(run.request_payload)
            prompt = str(request_payload.get("prompt") or "")

        # 请求内/历史落库统一强制 url 返回（否则 b64 会写进 DB，影响性能与存储）。
        request_payload["response_format"] = "url"
        request_payload.pop("kind", None)
        request_payload.pop("prompt", None)

        started_at = datetime.now(UTC)
        run.status = "running"
        run.started_at = started_at
        db.add(run)
        db.commit()

        if streaming:
            _append_run_event_and_publish_best_effort(
                db,
                redis=redis,
                run_id=UUID(str(run.id)),
                event_type="message.delta",
                payload={
                    "type": "message.delta",
                    "conversation_id": str(conv.id),
                    "assistant_message_id": assistant_message_id,
                    "delta": "正在生成图片…",
                    "kind": "image_generation",
                },
            )

        request = ImageGenerationRequest.model_validate({**request_payload, "prompt": prompt})

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60) as http_client:
                resp = await ImageAppService(
                    client=http_client,
                    redis=redis,
                    db=db,
                    api_key=auth_key,
                ).generate_image(request)
        except Exception as exc:
            finished_at = datetime.now(UTC)
            run.status = "failed"
            run.finished_at = finished_at
            run.latency_ms = int((time.perf_counter() - t0) * 1000)
            run.error_code = "IMAGE_GENERATION_FAILED"
            run.error_message = str(exc)[:512]
            db.add(run)
            db.commit()

            content = {
                "type": "image_generation",
                "status": "failed",
                "prompt": prompt,
                "params": request_payload,
                "images": [],
                "error": str(exc),
            }
            try:
                finalize_assistant_image_generation_after_user_sequence(
                    db,
                    conversation_id=UUID(str(conv.id)),
                    user_sequence=int(message.sequence or 0),
                    content=content,
                    preview_text=f"[图片生成失败] {prompt[:60]}",
                )
            except Exception:
                logger.exception("finalize image_generation message failed (run_id=%s)", run_id)

            _append_run_event_and_publish_best_effort(
                db,
                redis=redis,
                run_id=UUID(str(run.id)),
                event_type="message.failed",
                payload={
                    "type": "message.failed",
                    "conversation_id": str(conv.id),
                    "assistant_message_id": assistant_message_id,
                    "baseline_run": _run_to_summary(run),
                    "error": str(exc),
                    "kind": "image_generation",
                },
            )
            return "failed"

        finished_at = datetime.now(UTC)
        run.status = "succeeded"
        run.finished_at = finished_at
        run.latency_ms = int((time.perf_counter() - t0) * 1000)
        run.output_preview = f"[图片] {prompt[:60]}".strip()
        run.response_payload = resp.model_dump(mode="json")
        db.add(run)
        db.commit()

        images: list[dict[str, Any]] = []
        for item in resp.data or []:
            url = getattr(item, "url", None)
            revised = getattr(item, "revised_prompt", None)
            b64_json = getattr(item, "b64_json", None)
            if isinstance(url, str) and url:
                images.append(
                    {
                        "url": url,
                        "object_key": _extract_object_key_from_media_url(url),
                        "revised_prompt": revised,
                    }
                )
            elif isinstance(b64_json, str) and b64_json:
                images.append({"b64_json": b64_json, "revised_prompt": revised})

        stored_images: list[dict[str, Any]] = []
        for it in images:
            if isinstance(it.get("object_key"), str) and str(it["object_key"]).strip():
                stored_images.append(
                    {
                        "object_key": str(it["object_key"]).strip(),
                        "revised_prompt": it.get("revised_prompt"),
                    }
                )
                continue
            if isinstance(it.get("url"), str) and str(it["url"]).strip():
                stored_images.append(
                    {
                        "url": str(it["url"]).strip(),
                        "revised_prompt": it.get("revised_prompt"),
                    }
                )
                continue
            if isinstance(it.get("b64_json"), str) and str(it["b64_json"]).strip():
                # 兜底：极端情况下 OSS 写入失败且未生成 data URL，这里保留 b64_json（会增大 DB 体积）。
                stored_images.append(
                    {
                        "b64_json": str(it["b64_json"]).strip(),
                        "revised_prompt": it.get("revised_prompt"),
                    }
                )

        content = {
            "type": "image_generation",
            "status": "succeeded",
            "prompt": prompt,
            "params": request_payload,
            "images": stored_images,
            "created": int(getattr(resp, "created", None) or time.time()),
        }

        finalize_assistant_image_generation_after_user_sequence(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(message.sequence or 0),
            content=content,
            preview_text=f"[图片] {prompt[:60]}",
        )

        _append_run_event_and_publish_best_effort(
            db,
            redis=redis,
            run_id=UUID(str(run.id)),
            event_type="message.completed",
            payload={
                "type": "message.completed",
                "conversation_id": str(conv.id),
                "assistant_message_id": assistant_message_id,
                "baseline_run": _run_to_summary(run),
                "kind": "image_generation",
                "image_generation": {
                    "type": "image_generation",
                    "status": "succeeded",
                    "prompt": prompt,
                    "params": request_payload,
                    "images": images,
                    "created": int(getattr(resp, "created", None) or time.time()),
                },
            },
        )

        try:
            persist_run(db, run)
        except Exception:
            pass

        return "done"


@shared_task(name="tasks.execute_image_generation_run")
def execute_image_generation_run_task(
    run_id: str,
    assistant_message_id: str | None = None,
    streaming: bool = False,
) -> str:
    try:
        return asyncio.run(
            execute_image_generation_run(
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                streaming=bool(streaming),
            )
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("image_generation task failed: %s", exc)
        return "failed"


__all__ = ["execute_image_generation_run", "execute_image_generation_run_task"]
