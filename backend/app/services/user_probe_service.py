from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.models import Provider
from app.models.user_probe import UserProbeRun, UserProbeTask
from app.provider.config import get_provider_config
from app.provider.health import HealthStatus
from app.schemas import ProviderConfig, ProviderStatus
from app.services.provider_health_service import persist_provider_health
from app.services.user_probe_executor import ProbeApiStyle, execute_user_probe
from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Redis = object  # type: ignore[misc,assignment]


class UserProbeServiceError(RuntimeError):
    """用户探针任务相关错误。"""


class UserProbeNotFoundError(UserProbeServiceError):
    """探针任务/记录不存在。"""


class UserProbeConflictError(UserProbeServiceError):
    """探针任务状态冲突（例如正在执行）。"""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _clamp_prompt(prompt: str) -> str:
    value = (prompt or "").strip()
    if not value:
        raise UserProbeServiceError("prompt 不能为空")
    if len(value) > settings.user_probe_max_prompt_length:
        raise UserProbeServiceError(
            f"prompt 过长（>{settings.user_probe_max_prompt_length} 字符）"
        )
    return value


def _validate_interval(interval_seconds: int) -> int:
    if interval_seconds < settings.user_probe_min_interval_seconds:
        raise UserProbeServiceError(
            f"interval_seconds 过低（最小 {settings.user_probe_min_interval_seconds}s）"
        )
    if interval_seconds > settings.user_probe_max_interval_seconds:
        raise UserProbeServiceError(
            f"interval_seconds 过高（最大 {settings.user_probe_max_interval_seconds}s）"
        )
    return int(interval_seconds)


def _validate_max_tokens(max_tokens: int) -> int:
    if max_tokens < 1:
        raise UserProbeServiceError("max_tokens 必须 >= 1")
    if max_tokens > settings.user_probe_max_tokens_limit:
        raise UserProbeServiceError(
            f"max_tokens 过大（最大 {settings.user_probe_max_tokens_limit}）"
        )
    return int(max_tokens)


def _effective_max_tokens(value: int | None) -> int:
    if value is None:
        return int(settings.user_probe_default_max_tokens)
    return _validate_max_tokens(int(value))


def _load_provider_cfg(session: Session, provider_id: str) -> ProviderConfig:
    cfg = get_provider_config(provider_id, session=session)
    if cfg is None:
        raise UserProbeServiceError("无法构建 ProviderConfig（可能缺少可用的上游 API Key）")
    return cfg


def _count_user_tasks(session: Session, user_id: UUID) -> int:
    stmt = select(func.count()).select_from(UserProbeTask).where(UserProbeTask.user_id == user_id)
    return int(session.execute(stmt).scalar() or 0)


def create_user_probe_task(
    session: Session,
    *,
    user_id: UUID,
    provider: Provider,
    name: str,
    model_id: str,
    prompt: str,
    interval_seconds: int,
    max_tokens: int | None,
    api_style: ProbeApiStyle,
    enabled: bool,
) -> UserProbeTask:
    if settings.user_probe_max_tasks_per_user > 0:
        count = _count_user_tasks(session, user_id)
        if count >= settings.user_probe_max_tasks_per_user:
            raise UserProbeServiceError(
                f"已达到探针任务数量上限（{settings.user_probe_max_tasks_per_user}）"
            )

    prompt_value = _clamp_prompt(prompt)
    interval_value = _validate_interval(int(interval_seconds))
    tokens_value = _effective_max_tokens(max_tokens)

    if not model_id or not str(model_id).strip():
        raise UserProbeServiceError("model_id 不能为空")

    # 提前校验 ProviderConfig 以便尽早返回错误
    _load_provider_cfg(session, provider.provider_id)

    now = _now_utc()
    task = UserProbeTask(
        user_id=user_id,
        provider_uuid=provider.id,
        name=name.strip() or "probe",
        model_id=str(model_id).strip(),
        prompt=prompt_value,
        interval_seconds=interval_value,
        max_tokens=tokens_value,
        api_style=api_style,
        enabled=bool(enabled),
        in_progress=False,
        last_run_at=None,
        next_run_at=now if enabled else None,
        last_run_uuid=None,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def list_user_probe_tasks(
    session: Session,
    *,
    user_id: UUID,
    provider: Provider,
) -> list[UserProbeTask]:
    stmt: Select[tuple[UserProbeTask]] = (
        select(UserProbeTask)
        .where(UserProbeTask.user_id == user_id)
        .where(UserProbeTask.provider_uuid == provider.id)
        .options(selectinload(UserProbeTask.last_run))
        .order_by(UserProbeTask.created_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


def get_user_probe_task(
    session: Session,
    *,
    user_id: UUID,
    provider: Provider,
    task_id: UUID,
) -> UserProbeTask:
    stmt: Select[tuple[UserProbeTask]] = (
        select(UserProbeTask)
        .where(UserProbeTask.id == task_id)
        .where(UserProbeTask.user_id == user_id)
        .where(UserProbeTask.provider_uuid == provider.id)
        .options(selectinload(UserProbeTask.last_run))
    )
    task = session.execute(stmt).scalars().first()
    if task is None:
        raise UserProbeNotFoundError("探针任务不存在")
    return task


def update_user_probe_task(
    session: Session,
    *,
    task: UserProbeTask,
    name: str | None = None,
    model_id: str | None = None,
    prompt: str | None = None,
    interval_seconds: int | None = None,
    max_tokens: int | None = None,
    api_style: ProbeApiStyle | None = None,
    enabled: bool | None = None,
) -> UserProbeTask:
    if task.in_progress:
        raise UserProbeConflictError("任务正在执行，暂不可修改")

    touched_schedule = False
    if name is not None:
        task.name = name.strip() or task.name
    if model_id is not None:
        value = str(model_id).strip()
        if not value:
            raise UserProbeServiceError("model_id 不能为空")
        task.model_id = value
    if prompt is not None:
        task.prompt = _clamp_prompt(prompt)
    if interval_seconds is not None:
        task.interval_seconds = _validate_interval(int(interval_seconds))
        touched_schedule = True
    if max_tokens is not None:
        task.max_tokens = _validate_max_tokens(int(max_tokens))
        touched_schedule = True
    if api_style is not None:
        task.api_style = api_style
        touched_schedule = True

    if enabled is not None:
        previous = task.enabled
        task.enabled = bool(enabled)
        if previous is False and task.enabled is True:
            touched_schedule = True
        if task.enabled is False:
            task.next_run_at = None
            task.in_progress = False

    if touched_schedule and task.enabled:
        # 配置变更后让任务尽快生效（下一个 tick 会执行）
        task.next_run_at = _now_utc()

    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def delete_user_probe_task(session: Session, *, task: UserProbeTask) -> None:
    if task.in_progress:
        raise UserProbeConflictError("任务正在执行，暂不可删除")
    session.delete(task)
    session.commit()


def list_user_probe_runs(
    session: Session,
    *,
    task: UserProbeTask,
    limit: int = 20,
) -> list[UserProbeRun]:
    limit_value = max(1, min(int(limit), 200))
    stmt: Select[tuple[UserProbeRun]] = (
        select(UserProbeRun)
        .where(UserProbeRun.task_uuid == task.id)
        .order_by(UserProbeRun.created_at.desc())
        .limit(limit_value)
    )
    return list(session.execute(stmt).scalars().all())


def _status_from_probe_result(*, success: bool, status_code: int | None) -> ProviderStatus:
    if success:
        return ProviderStatus.HEALTHY
    if status_code is None:
        return ProviderStatus.DOWN
    if status_code >= 500:
        return ProviderStatus.DOWN
    if status_code >= 400:
        return ProviderStatus.DEGRADED
    return ProviderStatus.DEGRADED


async def run_user_probe_task_once(
    session: Session,
    *,
    task: UserProbeTask,
    provider: Provider,
    client: CurlCffiClient | httpx.AsyncClient,
    redis: Redis | None = None,
    allow_disabled: bool = False,
) -> UserProbeRun:
    if task.in_progress:
        raise UserProbeConflictError("任务正在执行，请稍后重试")

    if not task.enabled and not allow_disabled:
        raise UserProbeServiceError("任务已禁用")

    task.in_progress = True
    session.add(task)
    session.commit()

    return await _run_user_probe_task_in_progress(
        session,
        task=task,
        provider=provider,
        client=client,
        redis=redis,
    )


async def _run_user_probe_task_in_progress(
    session: Session,
    *,
    task: UserProbeTask,
    provider: Provider,
    client: CurlCffiClient | httpx.AsyncClient,
    redis: Redis | None,
) -> UserProbeRun:
    """
    执行一次探针任务，要求 task.in_progress 已经被置为 True 并持久化。

    该函数用于：
    - 手动“立即执行”接口（先置 in_progress 再调用）
    - 调度器批处理（先批量置 in_progress，再逐个调用）
    """
    cfg = _load_provider_cfg(session, provider.provider_id)

    started_at = _now_utc()
    try:
        result = await execute_user_probe(
            client,
            provider_cfg=cfg,
            model_id=task.model_id,
            prompt=task.prompt,
            max_tokens=task.max_tokens,
            api_style=task.api_style,  # type: ignore[arg-type]
            redis=redis,
        )
    finally:
        # 无论成功失败都要解除 in_progress
        task.in_progress = False

    finished_at = _now_utc()

    # 将“真实对话探针”结果同步到 Provider 健康状态（DB + 可选 Redis）。
    health_status = HealthStatus(
        provider_id=provider.provider_id,
        status=_status_from_probe_result(success=result.success, status_code=result.status_code),
        timestamp=finished_at.timestamp(),
        response_time_ms=float(result.latency_ms) if result.latency_ms is not None else None,
        error_message=result.error_message,
        last_successful_check=finished_at.timestamp() if result.success else None,
    )
    try:
        if redis is not None:
            await persist_provider_health(
                redis,
                session,
                provider,
                health_status,
                cache_ttl_seconds=settings.provider_health_cache_ttl_seconds,
            )
        else:
            provider.status = health_status.status.value
            provider.last_check = finished_at
            provider.metadata_json = {
                "response_time_ms": health_status.response_time_ms,
                "error_message": health_status.error_message,
                "last_successful_check": health_status.last_successful_check,
            }
            session.add(provider)
    except Exception:  # pragma: no cover - 健康状态写入失败不应阻断探针记录落库
        logger.exception(
            "user_probe: failed to persist provider health provider=%s task=%s",
            provider.provider_id,
            task.id,
        )

    run = UserProbeRun(
        task_uuid=task.id,
        user_id=task.user_id,
        provider_uuid=provider.id,
        model_id=task.model_id,
        api_style=result.api_style,
        success=result.success,
        status_code=result.status_code,
        latency_ms=result.latency_ms,
        error_message=result.error_message,
        response_text=result.response_text,
        response_excerpt=result.response_excerpt,
        response_json=result.response_json if isinstance(result.response_json, (dict, list)) else None,
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(run)
    session.flush()  # ensure run.id

    task.last_run_at = finished_at
    task.last_run_uuid = run.id
    task.next_run_at = (
        finished_at + timedelta(seconds=int(task.interval_seconds))
        if task.enabled
        else None
    )
    session.add(task)

    _prune_task_runs(session, task_id=task.id, keep=settings.user_probe_max_runs_per_task)

    session.commit()
    session.refresh(run)
    session.refresh(task)
    return run


def _prune_task_runs(session: Session, *, task_id: UUID, keep: int) -> None:
    keep_value = max(1, int(keep))
    # 找到需要删除的旧记录（按 created_at 逆序保留 keep 条）
    sub = (
        select(UserProbeRun.id)
        .where(UserProbeRun.task_uuid == task_id)
        .order_by(UserProbeRun.created_at.desc())
        .offset(keep_value)
    )
    ids = [row[0] for row in session.execute(sub).all()]
    if not ids:
        return
    session.execute(delete(UserProbeRun).where(UserProbeRun.id.in_(ids)))


async def run_due_user_probe_tasks(
    *,
    session: Session,
    redis: Redis | None = None,
    max_tasks: int | None = None,
) -> int:
    """
    扫描到期任务并执行。

    通过 `SELECT ... FOR UPDATE SKIP LOCKED` 避免多 worker 并发重复执行。
    """
    now = _now_utc()
    limit_value = int(max_tasks or settings.user_probe_max_due_tasks_per_tick)
    limit_value = max(1, limit_value)

    stmt = (
        select(UserProbeTask)
        .where(UserProbeTask.enabled.is_(True))
        .where(UserProbeTask.in_progress.is_(False))
        .where((UserProbeTask.next_run_at.is_(None)) | (UserProbeTask.next_run_at <= now))
        .order_by(UserProbeTask.next_run_at.asc().nullsfirst(), UserProbeTask.created_at.asc())
        .limit(limit_value)
        .with_for_update(skip_locked=True)
    )
    tasks: Sequence[UserProbeTask] = list(session.execute(stmt).scalars().all())
    if not tasks:
        return 0

    # 预先标记 in_progress，减少后续竞争；后续执行阶段不再做 in_progress 校验。
    for t in tasks:
        t.in_progress = True
    session.commit()

    processed = 0
    async with CurlCffiClient(
        timeout=settings.user_probe_timeout_seconds,
        impersonate="chrome120",
        trust_env=True,
    ) as client:
        for t in tasks:
            provider = session.get(Provider, t.provider_uuid)
            if provider is None:
                # provider 已被删除（理论上会 cascade），保护性跳过
                t.in_progress = False
                session.add(t)
                session.commit()
                continue

            # 仅允许 owner 的私有 Provider 参与任务执行；否则直接禁用任务
            if provider.owner_id != t.user_id:
                logger.warning(
                    "user_probe: provider ownership changed, disabling task=%s provider=%s user=%s",
                    t.id,
                    provider.provider_id,
                    t.user_id,
                )
                t.enabled = False
                t.in_progress = False
                t.next_run_at = None
                session.add(t)
                session.commit()
                continue

            try:
                await _run_user_probe_task_in_progress(
                    session,
                    task=t,
                    provider=provider,
                    client=client,
                    redis=redis,
                )
                processed += 1
            except Exception as exc:
                logger.exception("user_probe: run task failed task=%s err=%s", t.id, exc)
                t.in_progress = False
                # 避免失败任务被立即重复触发：失败也按 interval 推迟
                t.last_run_at = _now_utc()
                t.next_run_at = t.last_run_at + timedelta(seconds=int(t.interval_seconds))
                session.add(t)
                session.commit()

    return processed


__all__ = [
    "UserProbeConflictError",
    "UserProbeNotFoundError",
    "UserProbeServiceError",
    "create_user_probe_task",
    "delete_user_probe_task",
    "get_user_probe_task",
    "list_user_probe_runs",
    "list_user_probe_tasks",
    "run_due_user_probe_tasks",
    "run_user_probe_task_once",
    "update_user_probe_task",
]
