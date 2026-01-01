from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from celery import shared_task
from sqlalchemy import select

from app.auth import AuthenticatedAPIKey
from app.db.session import SessionLocal
from app.logging_config import logger
from app.models import APIKey, Conversation, Message, Run, User
from app.redis_client import close_redis_client_for_current_loop, get_redis_client
from app.repositories.run_event_repository import append_run_event
from app.schemas.video import VideoGenerationRequest
from app.services.chat_history_service import finalize_assistant_image_generation_after_user_sequence
from app.services.run_event_bus import build_run_event_envelope, publish_run_event, publish_run_event_best_effort
from app.services.video_app_service import VideoAppService
from app.services.video_task_cache import CachedTaskStatus, cache_task_status, invalidate_task_cache

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


async def _update_task_cache(
    redis: Redis,
    run: Run,
    *,
    progress: int | None = None,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """Update task status cache after status change."""
    try:
        entry = CachedTaskStatus(
            task_id=str(run.id),
            status=run.status,  # type: ignore[arg-type]
            created_at=run.created_at.isoformat() if run.created_at else "",
            started_at=run.started_at.isoformat() if run.started_at else None,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            progress=progress,
            result=result,
            error=error,
        )
        await cache_task_status(redis, entry)
    except Exception as exc:
        logger.debug("Failed to update task cache for %s: %s", run.id, exc)


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
            "video_generation task: append_run_event failed (run_id=%s type=%s)",
            run_id,
            event_type,
            exc_info=True,
        )
        return None


async def _append_run_event_and_publish(
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
        if redis is not None:
            await publish_run_event(
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
            "video_generation task: append_run_event failed (run_id=%s type=%s)",
            run_id,
            event_type,
            exc_info=True,
        )
        return None


async def execute_video_generation_run(
    *,
    run_id: str,
    assistant_message_id: str | None = None,
    streaming: bool = False,
) -> str:
    run_uuid = UUID(str(run_id))
    SessionFactory = SessionLocal

    redis = get_redis_client()
    try:
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
                        "delta": "正在生成视频…",
                        "kind": "video_generation",
                    },
                )

            request = VideoGenerationRequest.model_validate({**request_payload, "prompt": prompt})

            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as http_client:
                    resp = await VideoAppService(
                        client=http_client,
                        redis=redis,
                        db=db,
                        api_key=auth_key,
                    ).generate_video(request)
            except Exception as exc:
                finished_at = datetime.now(UTC)
                run.status = "failed"
                run.finished_at = finished_at
                run.latency_ms = int((time.perf_counter() - t0) * 1000)
                run.error_code = "VIDEO_GENERATION_FAILED"
                run.error_message = str(exc)[:512]
                db.add(run)
                db.commit()

                content = {
                    "type": "video_generation",
                    "status": "failed",
                    "prompt": prompt,
                    "params": request_payload,
                    "videos": [],
                    "error": str(exc),
                }
                try:
                    finalize_assistant_image_generation_after_user_sequence(
                        db,
                        conversation_id=UUID(str(conv.id)),
                        user_sequence=int(message.sequence or 0),
                        content=content,
                        preview_text=f"[视频生成失败] {prompt[:60]}",
                    )
                except Exception:
                    logger.exception("finalize video_generation message failed (run_id=%s)", run_id)

                await _append_run_event_and_publish(
                    db,
                    redis=redis,
                    run_id=UUID(str(run.id)),
                    event_type="message.failed",
                    payload={
                        "type": "message.failed",
                        "conversation_id": str(conv.id),
                        "assistant_message_id": assistant_message_id,
                        "baseline_run": _run_to_summary(run),
                        "kind": "video_generation",
                        "error": str(exc),
                    },
                )
                return "failed"

            finished_at = datetime.now(UTC)
            run.status = "succeeded"
            run.finished_at = finished_at
            run.latency_ms = int((time.perf_counter() - t0) * 1000)
            run.output_preview = f"[视频] {prompt[:60]}".strip()
            db.add(run)
            db.commit()

            videos: list[dict[str, Any]] = []
            stored_videos: list[dict[str, Any]] = []
            for item in resp.data or []:
                url = getattr(item, "url", None)
                object_key = getattr(item, "object_key", None)
                revised = getattr(item, "revised_prompt", None)
                entry: dict[str, Any] = {}
                if isinstance(url, str) and url:
                    entry["url"] = url
                if isinstance(object_key, str) and object_key:
                    entry["object_key"] = object_key
                    stored_videos.append({"object_key": object_key, "revised_prompt": revised})
                if revised is not None:
                    entry["revised_prompt"] = revised
                if entry:
                    videos.append(entry)

            content_with_urls = {
                "type": "video_generation",
                "status": "succeeded",
                "prompt": prompt,
                "params": request_payload,
                "videos": videos,
                "created": int(getattr(resp, "created", None) or time.time()),
            }
            stored_content = dict(content_with_urls)
            stored_content["videos"] = stored_videos

            try:
                finalize_assistant_image_generation_after_user_sequence(
                    db,
                    conversation_id=UUID(str(conv.id)),
                    user_sequence=int(message.sequence or 0),
                    content=stored_content,
                    preview_text=f"[视频] {prompt[:60]}",
                )
            except Exception:
                logger.exception("finalize video_generation message failed (run_id=%s)", run_id)

            run.response_payload = content_with_urls
            db.add(run)
            db.commit()

            await _append_run_event_and_publish(
                db,
                redis=redis,
                run_id=UUID(str(run.id)),
                event_type="message.completed",
                payload={
                    "type": "message.completed",
                    "conversation_id": str(conv.id),
                    "assistant_message_id": assistant_message_id,
                    "baseline_run": _run_to_summary(run),
                    "kind": "video_generation",
                    "video_generation": content_with_urls,
                },
            )
            return "succeeded"
    finally:
        try:
            await close_redis_client_for_current_loop()
        except Exception:
            pass


@shared_task(name="tasks.execute_video_generation_run")
def execute_video_generation_run_task(run_id: str, assistant_message_id: str | None = None, streaming: bool = False) -> str:
    try:
        return asyncio.run(
            execute_video_generation_run(run_id=run_id, assistant_message_id=assistant_message_id, streaming=streaming)
        )
    finally:
        try:
            asyncio.run(close_redis_client_for_current_loop())
        except Exception:
            pass


# ============= 独立视频生成任务（用于 /v1/videos/generations API） =============


async def execute_video_generation_standalone(
    *,
    run_id: str,
    api_key_id: str,
) -> str:
    """
    执行独立的视频生成任务（不依赖会话/消息上下文）。

    该函数用于处理通过 /v1/videos/generations API 创建的任务。
    与 execute_video_generation_run 不同，它不需要 conversation/message 上下文。
    """
    run_uuid = UUID(str(run_id))
    api_key_uuid = UUID(str(api_key_id))
    SessionFactory = SessionLocal

    redis = get_redis_client()
    try:
        with SessionFactory() as db:
            run = db.get(Run, run_uuid)
            if run is None:
                logger.warning("video_generation_standalone: run not found (run_id=%s)", run_id)
                return "skipped:no_run"

            if str(run.status or "") in {"succeeded", "failed", "canceled"}:
                return "skipped:already_finished"

            api_key = db.get(APIKey, api_key_uuid)
            if api_key is None:
                logger.warning("video_generation_standalone: api_key not found (api_key_id=%s)", api_key_id)
                run.status = "failed"
                run.error_code = "API_KEY_NOT_FOUND"
                run.error_message = "API Key not found"
                run.finished_at = datetime.now(UTC)
                db.add(run)
                db.commit()
                return "failed:no_api_key"

            try:
                auth_key = _to_authenticated_api_key(db, api_key=api_key)
            except RuntimeError as exc:
                run.status = "failed"
                run.error_code = "USER_NOT_FOUND"
                run.error_message = str(exc)[:512]
                run.finished_at = datetime.now(UTC)
                db.add(run)
                db.commit()
                return "failed:no_user"

            # 提取请求参数
            request_payload: dict[str, Any] = {}
            if isinstance(run.request_payload, dict):
                request_payload = dict(run.request_payload)

            prompt = str(request_payload.get("prompt") or "")
            request_payload.pop("kind", None)
            request_payload.pop("prompt", None)

            # 更新状态为 running
            started_at = datetime.now(UTC)
            run.status = "running"
            run.started_at = started_at
            db.add(run)
            db.commit()

            # 更新缓存：任务开始执行
            await _update_task_cache(redis, run, progress=5)

            # 构建请求并执行
            request = VideoGenerationRequest.model_validate({**request_payload, "prompt": prompt})

            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http_client:
                    resp = await VideoAppService(
                        client=http_client,
                        redis=redis,
                        db=db,
                        api_key=auth_key,
                    ).generate_video(request)
            except Exception as exc:
                finished_at = datetime.now(UTC)
                run.status = "failed"
                run.finished_at = finished_at
                run.latency_ms = int((time.perf_counter() - t0) * 1000)
                run.error_code = "VIDEO_GENERATION_FAILED"
                run.error_message = str(exc)[:512]
                db.add(run)
                db.commit()
                logger.exception("video_generation_standalone failed (run_id=%s): %s", run_id, exc)

                # 更新缓存：任务失败
                await _update_task_cache(
                    redis,
                    run,
                    progress=100,
                    error={"code": run.error_code, "message": run.error_message},
                )
                return "failed"

            # 成功：更新状态和结果
            finished_at = datetime.now(UTC)
            run.status = "succeeded"
            run.finished_at = finished_at
            run.latency_ms = int((time.perf_counter() - t0) * 1000)
            run.output_preview = f"[视频] {prompt[:60]}".strip()

            # 构建响应 payload
            videos: list[dict[str, Any]] = []
            for item in resp.data or []:
                url = getattr(item, "url", None)
                object_key = getattr(item, "object_key", None)
                revised = getattr(item, "revised_prompt", None)
                entry: dict[str, Any] = {}
                if isinstance(url, str) and url:
                    entry["url"] = url
                if isinstance(object_key, str) and object_key:
                    entry["object_key"] = object_key
                if revised is not None:
                    entry["revised_prompt"] = revised
                if entry:
                    videos.append(entry)

            run.response_payload = {
                "type": "video_generation",
                "status": "succeeded",
                "prompt": prompt,
                "params": request_payload,
                "videos": videos,
                "created": int(getattr(resp, "created", None) or time.time()),
            }
            db.add(run)
            db.commit()

            # 更新缓存：任务成功
            await _update_task_cache(
                redis,
                run,
                progress=100,
                result={
                    "created": run.response_payload.get("created"),
                    "data": videos,
                },
            )

            logger.info(
                "video_generation_standalone succeeded (run_id=%s, latency_ms=%d, videos=%d)",
                run_id,
                run.latency_ms or 0,
                len(videos),
            )
            return "succeeded"
    finally:
        try:
            await close_redis_client_for_current_loop()
        except Exception:
            pass


@shared_task(name="tasks.execute_video_generation_standalone")
def execute_video_generation_standalone_task(run_id: str, api_key_id: str) -> str:
    """
    Celery 任务：执行独立视频生成（用于 /v1/videos/generations API）。
    """
    try:
        return asyncio.run(
            execute_video_generation_standalone(run_id=run_id, api_key_id=api_key_id)
        )
    except Exception as exc:
        logger.exception("video_generation_standalone task failed: %s", exc)
        return "failed"
    finally:
        try:
            asyncio.run(close_redis_client_for_current_loop())
        except Exception:
            pass


__all__ = [
    "execute_video_generation_run",
    "execute_video_generation_run_task",
    "execute_video_generation_standalone",
    "execute_video_generation_standalone_task",
]

