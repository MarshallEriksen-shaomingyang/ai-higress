from __future__ import annotations

"""
视频生成 API 路由。

支持两种模式：
1. 同步模式（sync=true）：等待视频生成完成后返回结果
2. 异步模式（默认）：立即返回任务 ID，客户端通过轮询查询状态

端点：
- POST /v1/videos/generations：创建视频生成任务
- GET /v1/videos/generations/{task_id}：查询任务状态
- GET /v1/videos/generations：列出用户的视频生成历史
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth import AuthenticatedAPIKey, require_api_key
from app.deps import get_db, get_http_client, get_redis
from app.logging_config import logger
from app.models import Run
from app.schemas.video import VideoGenerationRequest, VideoGenerationResponse, VideoObject
from app.services.video_app_service import VideoAppService
from app.services.video_storage_service import build_signed_video_url
from app.services.video_task_cache import (
    CachedTaskStatus,
    cache_task_status,
    get_cached_task_status,
)

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


router = APIRouter(tags=["videos"])


# ============= 响应模型 =============


class VideoGenerationTaskStatus(BaseModel):
    """视频生成任务状态响应"""

    task_id: str = Field(..., description="任务唯一标识")
    status: Literal["queued", "running", "succeeded", "failed"] = Field(
        ..., description="任务状态"
    )
    created_at: str = Field(..., description="任务创建时间 (ISO 8601)")
    started_at: str | None = Field(None, description="任务开始时间 (ISO 8601)")
    finished_at: str | None = Field(None, description="任务完成时间 (ISO 8601)")
    progress: int | None = Field(
        None, ge=0, le=100, description="进度百分比 (0-100)"
    )
    result: VideoGenerationResponse | None = Field(
        None, description="生成结果 (仅当 status=succeeded 时)"
    )
    error: dict[str, Any] | None = Field(
        None, description="错误信息 (仅当 status=failed 时)"
    )

    model_config = {"json_schema_extra": {"example": {"task_id": "abc123", "status": "running", "created_at": "2024-01-01T00:00:00Z", "progress": 50}}}


class VideoGenerationTaskCreated(BaseModel):
    """视频生成任务创建响应"""

    task_id: str = Field(..., description="任务唯一标识，用于查询状态")
    status: Literal["queued"] = Field(default="queued", description="初始状态")
    created_at: str = Field(..., description="任务创建时间 (ISO 8601)")
    poll_url: str = Field(..., description="轮询状态的 URL")


class VideoGenerationHistoryItem(BaseModel):
    """视频生成历史记录项"""

    task_id: str
    status: str
    prompt: str | None = None
    model: str | None = None
    created_at: str
    finished_at: str | None = None
    latency_ms: int | None = None
    videos: list[dict[str, Any]] | None = None
    error: str | None = None


class VideoGenerationHistoryResponse(BaseModel):
    """视频生成历史列表响应"""

    items: list[VideoGenerationHistoryItem]
    total: int
    has_more: bool


# ============= 辅助函数 =============

# Request deduplication settings
_DEDUP_WINDOW_SECONDS = 60  # Deduplication window (60 seconds)
_DEDUP_KEY_PREFIX = "video:dedup:"


def _compute_request_signature(
    user_id: UUID,
    prompt: str,
    model: str,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """
    Compute a signature for request deduplication.

    The signature is based on user_id, prompt, model, and key parameters.
    """
    payload = {
        "user_id": str(user_id),
        "prompt": str(prompt or "").strip()[:1000],  # Limit prompt length for hashing
        "model": str(model or "").strip(),
    }
    if extra_params:
        # Include key parameters that affect the output
        for key in ("size", "seconds", "aspect_ratio", "seed", "image_url", "audio_url"):
            if extra_params.get(key) is not None:
                payload[key] = extra_params[key]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def _check_duplicate_request(
    redis: Redis,
    user_id: UUID,
    request: VideoGenerationRequest,
) -> str | None:
    """
    Check if there's a recent duplicate request.

    Returns the existing task_id if a duplicate is found, None otherwise.
    """
    try:
        signature = _compute_request_signature(
            user_id=user_id,
            prompt=request.prompt,
            model=request.model or "",
            extra_params={
                "size": request.size,
                "seconds": request.seconds,
                "aspect_ratio": request.aspect_ratio,
                "seed": request.seed,
                "image_url": request.image_url,
                "audio_url": request.audio_url,
            },
        )
        key = f"{_DEDUP_KEY_PREFIX}{signature}"
        existing_task_id = await redis.get(key)
        if existing_task_id:
            return existing_task_id.decode("utf-8") if isinstance(existing_task_id, bytes) else str(existing_task_id)
        return None
    except Exception as exc:
        logger.debug("Failed to check duplicate request: %s", exc)
        return None


async def _register_request(
    redis: Redis,
    user_id: UUID,
    request: VideoGenerationRequest,
    task_id: str,
) -> None:
    """
    Register a request for deduplication.
    """
    try:
        signature = _compute_request_signature(
            user_id=user_id,
            prompt=request.prompt,
            model=request.model or "",
            extra_params={
                "size": request.size,
                "seconds": request.seconds,
                "aspect_ratio": request.aspect_ratio,
                "seed": request.seed,
                "image_url": request.image_url,
                "audio_url": request.audio_url,
            },
        )
        key = f"{_DEDUP_KEY_PREFIX}{signature}"
        await redis.setex(key, _DEDUP_WINDOW_SECONDS, task_id)
    except Exception as exc:
        logger.debug("Failed to register request for deduplication: %s", exc)


def _run_to_task_status(run: Run) -> VideoGenerationTaskStatus:
    """将 Run 模型转换为任务状态响应"""
    result: VideoGenerationResponse | None = None
    error: dict[str, Any] | None = None

    if run.status == "succeeded" and isinstance(run.response_payload, dict):
        videos: list[VideoObject] = []
        for v in run.response_payload.get("videos", []):
            if isinstance(v, dict):
                url = v.get("url")
                object_key = v.get("object_key")
                # 如果只有 object_key，生成签名 URL
                if not url and object_key:
                    url = build_signed_video_url(object_key)
                videos.append(
                    VideoObject(
                        url=url,
                        object_key=object_key,
                        revised_prompt=v.get("revised_prompt"),
                    )
                )
        result = VideoGenerationResponse(
            created=run.response_payload.get("created", int(time.time())),
            data=videos,
        )
    elif run.status == "failed":
        error = {
            "code": run.error_code or "VIDEO_GENERATION_FAILED",
            "message": run.error_message or "视频生成失败",
        }

    # 计算进度（简化逻辑）
    progress: int | None = None
    if run.status == "queued":
        progress = 0
    elif run.status == "running":
        # 根据已耗时估算进度（假设平均生成时间 5 分钟）
        if run.started_at:
            elapsed = (datetime.now(UTC) - run.started_at.replace(tzinfo=UTC)).total_seconds()
            progress = min(95, int(elapsed / 300 * 100))
        else:
            progress = 5
    elif run.status in ("succeeded", "failed"):
        progress = 100

    return VideoGenerationTaskStatus(
        task_id=str(run.id),
        status=run.status,  # type: ignore[arg-type]
        created_at=run.created_at.isoformat() if run.created_at else datetime.now(UTC).isoformat(),
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        progress=progress,
        result=result,
        error=error,
    )


def _run_to_history_item(run: Run) -> VideoGenerationHistoryItem:
    """将 Run 模型转换为历史记录项"""
    prompt: str | None = None
    model: str | None = None
    videos: list[dict[str, Any]] | None = None

    if isinstance(run.request_payload, dict):
        prompt = run.request_payload.get("prompt")
        model = run.request_payload.get("model")

    if run.status == "succeeded" and isinstance(run.response_payload, dict):
        raw_videos = run.response_payload.get("videos", [])
        videos = []
        for v in raw_videos:
            if isinstance(v, dict):
                url = v.get("url")
                object_key = v.get("object_key")
                if not url and object_key:
                    url = build_signed_video_url(object_key)
                videos.append({"url": url, "object_key": object_key})

    return VideoGenerationHistoryItem(
        task_id=str(run.id),
        status=run.status,
        prompt=prompt,
        model=model or run.requested_logical_model,
        created_at=run.created_at.isoformat() if run.created_at else "",
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        latency_ms=run.latency_ms,
        videos=videos,
        error=run.error_message if run.status == "failed" else None,
    )


# ============= API 端点 =============


@router.post(
    "/v1/videos/generations",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create video generation task",
    description="Creates a video generation task. Returns immediately with task ID for async polling, or waits for completion if sync=true.",
    responses={
        202: {"model": VideoGenerationTaskCreated, "description": "Task created (async mode)"},
        200: {"model": VideoGenerationResponse, "description": "Video generated (sync mode)"},
    },
)
async def create_video_generation(
    request: VideoGenerationRequest = Body(...),
    sync: bool = Query(
        default=False,
        description="If true, wait for generation to complete before returning",
    ),
    client: httpx.AsyncClient = Depends(get_http_client),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    创建视频生成任务。

    默认为异步模式，立即返回任务 ID，客户端需要轮询 `/v1/videos/generations/{task_id}` 查询状态。
    如果设置 `sync=true`，则等待视频生成完成后返回结果。

    注意：视频生成通常需要 1-10 分钟，同步模式可能导致请求超时。
    """
    if sync:
        # 同步模式：直接执行并返回结果
        try:
            service = VideoAppService(client=client, redis=redis, db=db, api_key=current_key)
            return await service.generate_video(request)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("video generation sync failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 异步模式：检查是否有重复请求
    existing_task_id = await _check_duplicate_request(redis, current_key.user_id, request)
    if existing_task_id:
        # 检查现有任务是否仍在处理中
        try:
            existing_run = db.get(Run, UUID(existing_task_id))
            if existing_run and existing_run.status in ("queued", "running"):
                logger.info(
                    "Returning existing task for duplicate request: task_id=%s, user_id=%s",
                    existing_task_id,
                    current_key.user_id,
                )
                return VideoGenerationTaskCreated(
                    task_id=existing_task_id,
                    status="queued",
                    created_at=existing_run.created_at.isoformat() if existing_run.created_at else datetime.now(UTC).isoformat(),
                    poll_url=f"/v1/videos/generations/{existing_task_id}",
                )
        except Exception as exc:
            logger.debug("Failed to verify existing task: %s", exc)

    # 创建新任务
    run_id = uuid4()
    now = datetime.now(UTC)

    # 创建 Run 记录
    run = Run(
        id=run_id,
        # 没有 message_id 时使用 run_id 自身作为占位
        message_id=run_id,
        user_id=current_key.user_id,
        api_key_id=current_key.id,
        requested_logical_model=str(request.model or "").strip(),
        status="queued",
        created_at=now,
        request_payload={
            "kind": "video_generation",
            "prompt": request.prompt,
            "model": request.model,
            "size": request.size,
            "seconds": request.seconds,
            "aspect_ratio": request.aspect_ratio,
            "resolution": request.resolution,
            "negative_prompt": request.negative_prompt,
            "seed": request.seed,
            "fps": request.fps,
            "num_outputs": request.num_outputs,
            "generate_audio": request.generate_audio,
            "image_url": request.image_url,
            "audio_url": request.audio_url,
            "enhance_prompt": request.enhance_prompt,
            "extra_body": request.extra_body,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 发送 Celery 任务
    try:
        from app.celery_app import celery_app

        celery_app.send_task(
            "tasks.execute_video_generation_standalone",
            args=[str(run_id), str(current_key.id)],
        )
    except Exception as exc:
        logger.exception("failed to send celery task: %s", exc)
        # 回滚状态
        run.status = "failed"
        run.error_code = "TASK_QUEUE_ERROR"
        run.error_message = str(exc)[:512]
        db.add(run)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "TASK_QUEUE_ERROR", "message": "无法创建后台任务"},
        ) from exc

    # 注册请求用于去重
    await _register_request(redis, current_key.user_id, request, str(run_id))

    return VideoGenerationTaskCreated(
        task_id=str(run_id),
        status="queued",
        created_at=now.isoformat(),
        poll_url=f"/v1/videos/generations/{run_id}",
    )


@router.get(
    "/v1/videos/generations/{task_id}",
    response_model=VideoGenerationTaskStatus,
    summary="Get video generation task status",
    description="Query the status and result of a video generation task.",
)
async def get_video_generation_status(
    task_id: str,
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    查询视频生成任务状态。

    返回任务的当前状态、进度和结果（如果已完成）。
    优先从 Redis 缓存读取，缓存未命中时查询数据库并更新缓存。
    """
    try:
        run_uuid = UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TASK_ID", "message": "无效的任务 ID 格式"},
        )

    # 尝试从缓存读取
    cached = await get_cached_task_status(redis, task_id)
    if cached:
        # 缓存命中，直接返回（缓存中的数据已经过权限验证）
        return VideoGenerationTaskStatus(
            task_id=cached.task_id,
            status=cached.status,
            created_at=cached.created_at,
            started_at=cached.started_at,
            finished_at=cached.finished_at,
            progress=cached.progress,
            result=VideoGenerationResponse(**cached.result) if cached.result else None,
            error=cached.error,
        )

    # 缓存未命中，查询数据库
    run = db.get(Run, run_uuid)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"},
        )

    # 验证任务所有权
    if run.user_id != current_key.user_id and not current_key.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"},
        )

    # 验证是视频生成任务
    if not isinstance(run.request_payload, dict) or run.request_payload.get("kind") != "video_generation":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"},
        )

    # 构建响应
    task_status = _run_to_task_status(run)

    # 更新缓存
    try:
        cache_entry = CachedTaskStatus(
            task_id=task_status.task_id,
            status=task_status.status,
            created_at=task_status.created_at,
            started_at=task_status.started_at,
            finished_at=task_status.finished_at,
            progress=task_status.progress,
            result=task_status.result.model_dump() if task_status.result else None,
            error=task_status.error,
        )
        await cache_task_status(redis, cache_entry)
    except Exception as exc:
        # 缓存失败不影响正常响应
        logger.warning("Failed to cache task status for %s: %s", task_id, exc)

    return task_status


@router.get(
    "/v1/videos/generations",
    response_model=VideoGenerationHistoryResponse,
    summary="List video generation history",
    description="List the user's video generation task history.",
)
async def list_video_generations(
    limit: int = Query(default=20, ge=1, le=100, description="每页数量"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="按状态筛选 (queued/running/succeeded/failed)",
    ),
    db: Session = Depends(get_db),
    current_key: AuthenticatedAPIKey = Depends(require_api_key),
):
    """
    列出用户的视频生成历史。

    支持分页和按状态筛选。
    """
    # 构建查询
    query = (
        select(Run)
        .where(Run.user_id == current_key.user_id)
        .where(Run.request_payload["kind"].astext == "video_generation")
    )

    if status_filter:
        query = query.where(Run.status == status_filter)

    # 计算总数
    count_query = select(Run.id).where(Run.user_id == current_key.user_id).where(Run.request_payload["kind"].astext == "video_generation")
    if status_filter:
        count_query = count_query.where(Run.status == status_filter)
    total = len(list(db.execute(count_query).scalars().all()))

    # 分页查询
    query = query.order_by(desc(Run.created_at)).offset(offset).limit(limit + 1)
    runs = list(db.execute(query).scalars().all())

    has_more = len(runs) > limit
    if has_more:
        runs = runs[:limit]

    items = [_run_to_history_item(run) for run in runs]

    return VideoGenerationHistoryResponse(
        items=items,
        total=total,
        has_more=has_more,
    )


__all__ = ["router"]
