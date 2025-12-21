from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal as _AppSessionLocal
from app.deps import get_db, get_http_client, get_redis
from app.errors import not_found
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.logging_config import logger
from app.models import Eval as EvalModel
from app.models import Message as MessageModel
from app.models import Run as RunModel
from app.schemas import EvalCreateRequest, EvalRatingRequest, EvalRatingResponse, EvalResponse
from app.services.chat_history_service import get_assistant, get_conversation
from app.services.eval_service import (
    _background_http_client,
    _maybe_mark_eval_ready,
    _to_authenticated_api_key,
    create_eval,
    execute_run_stream,
    submit_rating,
)
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
    resolve_project_context,
)

router = APIRouter(
    tags=["evals"],
    dependencies=[Depends(require_jwt_token)],
)

# Backward-compatible hook for tests:
# - tests may patch `app.api.v1.eval_routes.SessionLocal` to control DB sessions in streaming tasks.
# - runtime code should prefer building a sessionmaker from the current request-scoped Session bind.
SessionLocal = _AppSessionLocal

def _build_stream_session_factory(db: Session):
    if SessionLocal is not _AppSessionLocal:
        return SessionLocal
    bind = db.get_bind()
    return sessionmaker(bind=bind, autoflush=False, autocommit=False, future=True)

def _encode_sse_event(*, event_type: str, data: Any) -> bytes:
    """
    Encode a single SSE event frame.

    We send both:
    - `event: <type>` so standard SSE clients can dispatch by event name;
    - `data: <json>` where json includes `type` for backward compatibility.
    """
    lines: list[str] = []
    event = str(event_type or "").strip()
    if event:
        lines.append(f"event: {event}")

    if isinstance(data, (bytes, bytearray)):
        payload = data.decode("utf-8", errors="ignore")
        lines.append(f"data: {payload}")
    elif isinstance(data, str):
        lines.append(f"data: {data}")
    else:
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")

    return ("\n".join(lines) + "\n\n").encode("utf-8")


def _run_to_summary(run) -> dict:
    return {
        "run_id": run.id,
        "requested_logical_model": run.requested_logical_model,
        "status": run.status,
        "output_preview": run.output_preview,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
    }


@router.post("/v1/evals")
async def create_eval_endpoint(
    payload: EvalCreateRequest,
    db: Session = Depends(get_db),
    redis: Any = Depends(get_redis),
    client: Any = Depends(get_http_client),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Any:
    eval_obj, challenger_runs, explanation = await create_eval(
        db,
        redis=redis,
        client=client,
        current_user=current_user,
        project_id=payload.project_id,
        assistant_id=payload.assistant_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        baseline_run_id=payload.baseline_run_id,
        start_background_runs=not bool(payload.streaming),
    )

    if not payload.streaming:
        return EvalResponse(
            eval_id=eval_obj.id,
            status=eval_obj.status,
            baseline_run_id=eval_obj.baseline_run_id,
            challengers=[_run_to_summary(r) for r in challenger_runs],
            explanation=explanation,
            created_at=eval_obj.created_at,
            updated_at=eval_obj.updated_at,
        )

    # 计算 stream 执行所需的上下文，并尽量提前释放 request-scoped 资源（db/http client）。
    # 注意：StreamingResponse 生命周期很长，后续并发任务需要独立 Session，
    # 但必须与当前请求使用同一 bind（否则测试注入的 in-memory DB/生产 DB 不一致会导致查不到数据）。
    BackgroundSessionLocal = _build_stream_session_factory(db)

    ctx = resolve_project_context(db, project_id=payload.project_id, current_user=current_user)
    cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)
    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )
    auth = _to_authenticated_api_key(db, api_key=ctx.api_key)
    eval_id = UUID(str(eval_obj.id))
    eval_status = str(eval_obj.status)
    user_id = UUID(str(current_user.id))
    conversation_id = UUID(str(payload.conversation_id))
    assistant_id = UUID(str(payload.assistant_id))
    message_id = UUID(str(payload.message_id))
    challenger_run_ids = [UUID(str(r.id)) for r in challenger_runs]
    challengers_initial = [
        {k: (str(v) if isinstance(v, UUID) else v) for k, v in _run_to_summary(r).items()}
        for r in challenger_runs
    ]
    baseline_run_id_str = str(eval_obj.baseline_run_id)
    explanation_payload = explanation

    # 释放 db/http client（StreamingResponse 生命周期很长，避免一直占用 request-scoped 资源）
    try:
        db.close()
    except Exception:
        pass
    try:
        await client.__aexit__(None, None, None)  # type: ignore[attr-defined]
    except Exception:
        pass

    # 流式模式：真并行执行 challenger runs 并通过 SSE 返回
    async def _stream_generator():
        run_tasks: list[asyncio.Task[None]] = []
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        try:
            # 1. 首先返回 Eval 对象基本信息
            initial_data = {
                "type": "eval.created",
                "eval_id": str(eval_id),
                "status": eval_status,
                "baseline_run_id": baseline_run_id_str,
                "challengers": challengers_initial,
                "explanation": explanation_payload,
            }
            yield _encode_sse_event(event_type="eval.created", data=initial_data)

            def _emit_run_snapshot(run_row: RunModel) -> dict[str, Any] | None:
                if run_row.status == "succeeded":
                    return {
                        "run_id": str(run_row.id),
                        "type": "run.completed",
                        "status": "succeeded",
                        "provider_id": run_row.selected_provider_id,
                        "provider_model": run_row.selected_provider_model,
                        "cost_credits": run_row.cost_credits,
                        "latency_ms": run_row.latency_ms,
                        "full_text": run_row.output_text,
                    }
                if run_row.status in {"failed", "cancelled"}:
                    err_obj: dict[str, Any] | None = None
                    if isinstance(run_row.response_payload, dict) and isinstance(run_row.response_payload.get("error"), dict):
                        err_obj = run_row.response_payload.get("error")  # type: ignore[assignment]
                    if err_obj is None:
                        err_obj = {"message": run_row.error_message or "run_failed"}
                    return {
                        "run_id": str(run_row.id),
                        "type": "run.error",
                        "status": "failed" if run_row.status == "failed" else run_row.status,
                        "error_code": run_row.error_code,
                        "error": err_obj,
                    }
                return None

            # 2) 先把已完成/失败的 challenger 直接发 snapshot；queued 才执行（避免重复跑/重复计费）
            # 这里优先使用 create_eval 返回的 challenger_runs（避免在测试环境里 SessionLocal 被 mock 后
            # .all() 结果不可用导致无法启动任务），必要时再依赖后续的 polling 兜底。
            to_execute: list[UUID] = []
            unfinished: set[UUID] = set()
            for row in challenger_runs:
                try:
                    rid = UUID(str(row.id))
                except Exception:
                    continue
                if row.status == "queued":
                    to_execute.append(rid)
                    unfinished.add(rid)
                elif row.status == "running":
                    unfinished.add(rid)
                else:
                    snap = _emit_run_snapshot(row)
                    if snap is not None:
                        await queue.put(snap)

            async def _run_task(run_id: UUID) -> None:
                try:
                    # 每个 run 独立 session，避免同一 Session 在多个并发任务中交叉使用导致报错
                    with BackgroundSessionLocal() as task_db:
                        task_run = (
                            task_db.execute(select(RunModel).where(RunModel.id == run_id))
                            .scalars()
                            .first()
                        )
                        if task_run is None:
                            await queue.put(
                                {
                                    "run_id": str(run_id),
                                    "type": "run.error",
                                    "status": "failed",
                                    "error_code": "NOT_FOUND",
                                    "error": {"message": "run not found"},
                                }
                            )
                            return

                        if task_run.status != "queued":
                            snap = _emit_run_snapshot(task_run)
                            if snap is not None:
                                await queue.put(snap)
                            return

                        conv = get_conversation(
                            task_db,
                            conversation_id=conversation_id,
                            user_id=user_id,
                        )
                        assistant = get_assistant(
                            task_db,
                            assistant_id=assistant_id,
                            user_id=user_id,
                        )
                        user_message = (
                            task_db.execute(select(MessageModel).where(MessageModel.id == message_id))
                            .scalars()
                            .first()
                        )

                        if conv is None or assistant is None or user_message is None:
                            logger.error("eval_routes: context objects not found for run %s", run_id)
                            task_run.status = "failed"
                            task_run.error_code = "NOT_FOUND"
                            task_run.error_message = "Context objects not found"
                            task_run.response_payload = {"error": {"type": "NOT_FOUND", "message": task_run.error_message}}
                            task_run.finished_at = datetime.now(UTC)
                            task_db.add(task_run)
                            task_db.commit()
                            await queue.put(
                                {
                                    "run_id": str(run_id),
                                    "type": "run.error",
                                    "status": "failed",
                                    "error_code": "NOT_FOUND",
                                    "error": {"message": "Context objects not found"},
                                }
                            )
                            return

                        async with _background_http_client() as task_client:
                            async for item in execute_run_stream(
                                task_db,
                                redis=redis,
                                client=task_client,
                                api_key=auth,
                                effective_provider_ids=effective_provider_ids,
                                conversation=conv,
                                assistant=assistant,
                                user_message=user_message,
                                run=task_run,
                                requested_logical_model=task_run.requested_logical_model,
                                payload_override=dict(task_run.request_payload or {}),
                            ):
                                await queue.put(item)
                except asyncio.CancelledError:
                    raise
                except Exception as task_exc:
                    logger.exception("eval_routes: run_task failed for run %s", run_id)
                    # best-effort 落库（对齐 poll 路径）
                    try:
                        with BackgroundSessionLocal() as err_db:
                            err_run = (
                                err_db.execute(select(RunModel).where(RunModel.id == run_id))
                                .scalars()
                                .first()
                            )
                            if err_run is not None and err_run.status in {"queued", "running"}:
                                err_run.status = "failed"
                                err_run.error_code = "INTERNAL_ERROR"
                                err_run.error_message = str(task_exc)
                                err_run.response_payload = {"error": {"type": "INTERNAL_ERROR", "message": str(task_exc)}}
                                err_run.finished_at = datetime.now(UTC)
                                err_db.add(err_run)
                                err_db.commit()
                    except Exception:
                        logger.info("eval_routes: failed to persist run error snapshot", exc_info=True)
                    await queue.put(
                        {
                            "run_id": str(run_id),
                            "type": "run.error",
                            "status": "failed",
                            "error_code": "INTERNAL_ERROR",
                            "error": {"message": str(task_exc)},
                        }
                    )

            # 启动所有 queued run
            run_tasks = [asyncio.create_task(_run_task(run_id)) for run_id in to_execute]

            num_tasks = len(run_tasks)
            while True:
                finished_tasks = sum(1 for t in run_tasks if t.done())
                if finished_tasks >= num_tasks and queue.empty() and not unfinished:
                    break

                try:
                    # 使用 wait_for 实现 heartbeat
                    item = await asyncio.wait_for(queue.get(), timeout=10.0)
                    event_type = "message"
                    if isinstance(item, dict):
                        event_type = str(item.get("type") or "message")
                        if event_type in {"run.completed", "run.error"}:
                            run_id_str = item.get("run_id")
                            try:
                                unfinished.discard(UUID(str(run_id_str)))
                            except Exception:
                                pass
                    yield _encode_sse_event(event_type=event_type, data=item)
                except TimeoutError:
                    # best-effort：观察非本次请求启动的 running 任务，捕捉其最终态
                    if unfinished:
                        try:
                            with BackgroundSessionLocal() as poll_db:
                                polled = list(
                                    poll_db.execute(select(RunModel).where(RunModel.id.in_(list(unfinished))))
                                    .scalars()
                                    .all()
                                )
                            for row in polled:
                                if row.status in {"succeeded", "failed", "cancelled"}:
                                    unfinished.discard(UUID(str(row.id)))
                                    snap = _emit_run_snapshot(row)
                                    if snap is not None:
                                        await queue.put(snap)
                        except Exception:
                            logger.info("eval_routes: polling unfinished runs failed", exc_info=True)
                    yield _encode_sse_event(
                        event_type="heartbeat",
                        data={"type": "heartbeat", "ts": int(time.time())},
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("eval_routes: error getting from queue")

            # 检查是否全部 ready
            with BackgroundSessionLocal() as final_db:
                _maybe_mark_eval_ready(final_db, eval_id=eval_id)
                final_db.commit()
                eval_row = final_db.execute(select(EvalModel).where(EvalModel.id == eval_id)).scalars().first()
                final_status = str(eval_row.status) if eval_row is not None else "ready"

            final_data = {
                "type": "eval.completed",
                "eval_id": str(eval_id),
                "status": final_status,
            }
            yield _encode_sse_event(event_type="eval.completed", data=final_data)
            yield _encode_sse_event(event_type="done", data="[DONE]")

        except asyncio.CancelledError:
            # 客户端断开时不发送 eval.error，直接触发 finally 做 cancel/回收。
            raise
        except Exception as e:
            logger.exception("eval_routes: stream generator failed")
            yield _encode_sse_event(
                event_type="eval.error",
                data={"type": "eval.error", "error": {"message": str(e)}},
            )
        finally:
            # 确保所有任务被取消
            for t in run_tasks:
                if not t.done():
                    t.cancel()
            if run_tasks:
                # 给一点时间让任务响应取消
                await asyncio.gather(*run_tasks, return_exceptions=True)

    return StreamingResponse(_stream_generator(), media_type="text/event-stream")


@router.get("/v1/evals/{eval_id}", response_model=EvalResponse)
def get_eval_endpoint(
    eval_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> EvalResponse:
    eval_row = db.execute(
        select(EvalModel).where(
            EvalModel.id == eval_id,
            EvalModel.user_id == UUID(str(current_user.id)),
        )
    ).scalars().first()
    if eval_row is None:
        raise not_found("评测不存在", details={"eval_id": str(eval_id)})

    challenger_ids = []
    if isinstance(eval_row.challenger_run_ids, list):
        for item in eval_row.challenger_run_ids:
            try:
                challenger_ids.append(UUID(str(item)))
            except ValueError:
                continue

    challengers = []
    if challenger_ids:
        challengers = list(
            db.execute(select(RunModel).where(RunModel.id.in_(challenger_ids))).scalars().all()
        )

    return EvalResponse(
        eval_id=eval_row.id,
        status=eval_row.status,
        baseline_run_id=eval_row.baseline_run_id,
        challengers=[_run_to_summary(r) for r in challengers],
        explanation=eval_row.explanation,
        created_at=eval_row.created_at,
        updated_at=eval_row.updated_at,
    )


@router.post("/v1/evals/{eval_id}/rating", response_model=EvalRatingResponse)
def submit_eval_rating_endpoint(
    eval_id: UUID,
    payload: EvalRatingRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> EvalRatingResponse:
    rating = submit_rating(
        db,
        current_user=current_user,
        eval_id=eval_id,
        winner_run_id=payload.winner_run_id,
        reason_tags=payload.reason_tags,
    )
    return EvalRatingResponse(
        eval_id=rating.eval_id,
        winner_run_id=rating.winner_run_id,
        reason_tags=list(rating.reason_tags or []),
        created_at=rating.created_at,
    )


__all__ = ["router"]
