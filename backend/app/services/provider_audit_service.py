from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import anyio
from sqlalchemy.orm import Session

from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.models import (
    Provider,
    ProviderAuditLog,
    ProviderTestRecord,
)
from app.provider.config import get_provider_config
from app.provider.health import HealthStatus
from app.redis_client import get_redis_client
from app.schemas import ProviderStatus
from app.repositories.provider_audit_repository import (
    commit_refresh as repo_commit_refresh,
    get_latest_test_record as repo_get_latest_test_record,
    get_provider_by_provider_id as repo_get_provider_by_provider_id,
    list_audit_logs as repo_list_audit_logs,
    list_test_records as repo_list_test_records,
    persist_provider_audit_log as repo_persist_provider_audit_log,
    persist_provider_test_record as repo_persist_provider_test_record,
)
from app.services.provider_health_service import persist_provider_health
from app.services.user_probe_executor import execute_user_probe
from app.settings import settings

AUDIT_STATES = {"pending", "testing", "approved", "rejected", "approved_limited"}
OPERATION_STATES = {"active", "paused", "offline"}


class ProviderAuditError(RuntimeError):
    """基础审核错误。"""


class ProviderNotFoundError(ProviderAuditError):
    """未找到 Provider。"""


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


def _pick_probe_model(provider: Provider, cfg) -> str | None:
    probe_model = getattr(provider, "probe_model", None) or getattr(cfg, "probe_model", None)
    if isinstance(probe_model, str) and probe_model.strip():
        return probe_model.strip()

    static_models = getattr(cfg, "static_models", None) or []
    if isinstance(static_models, list):
        for item in static_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("model_id") or item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                return model_id.strip()
    return None


def _get_provider(session: Session, provider_id: str) -> Provider:
    provider = repo_get_provider_by_provider_id(session, provider_id=provider_id)
    if provider is None:
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    return provider


def _record_audit_log(
    session: Session,
    provider: Provider,
    action: str,
    *,
    operator_id: UUID | None,
    remark: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    operation_from_status: str | None = None,
    operation_to_status: str | None = None,
    test_record: ProviderTestRecord | None = None,
) -> ProviderAuditLog:
    log = ProviderAuditLog(
        provider_uuid=provider.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        operation_from_status=operation_from_status,
        operation_to_status=operation_to_status,
        operator_id=operator_id,
        remark=remark,
        test_record_uuid=test_record.id if test_record else None,
    )
    repo_persist_provider_audit_log(session, log=log)
    return log


def trigger_provider_test(
    session: Session,
    provider_id: str,
    operator_id: UUID | None,
    *,
    mode: Literal["auto", "custom", "cron"] = "auto",
    remark: str | None = None,
    custom_input: str | None = None,
) -> ProviderTestRecord:
    """触发一次受控探针测试并写入测试记录。

    当前实现复用“真实对话探针”执行器：对上游发起一次最小对话请求，并落库/缓存。
    """

    provider = _get_provider(session, provider_id)
    previous_status = provider.audit_status
    provider.audit_status = "testing"

    started_at = datetime.now(UTC)
    probe_status = None
    latency_ms: int | None = None
    error_code: str | None = None
    effective_prompt = custom_input or settings.probe_prompt
    probe_model = getattr(provider, "probe_model", None)

    cfg = get_provider_config(provider_id, session=session)
    if cfg is None:
        # 无法构建可用配置（通常是缺少 API Key 或配置不完整），返回一条失败的测试记录避免 404。
        logger.warning("Provider %s config missing; skipping real probe", provider_id)
        finished_at = datetime.now(UTC)
        record = ProviderTestRecord(
            provider_uuid=provider.id,
            mode=mode,
            success=False,
            summary="provider config missing",
            probe_results=[
                {
                    "case": "health_check",
                    "mode": mode,
                    "model": probe_model,
                    "input": effective_prompt,
                    "status": "config_missing",
                    "latency_ms": None,
                    "timestamp": finished_at.isoformat(),
                }
            ],
            latency_ms=None,
            error_code="config_missing",
            cost=0.0,
            started_at=started_at,
            finished_at=finished_at,
        )
        repo_persist_provider_test_record(session, record=record)
        _record_audit_log(
            session,
            provider,
            "test",
            operator_id=operator_id,
            remark=remark,
            from_status=previous_status,
            to_status=provider.audit_status,
            test_record=record,
        )
        repo_commit_refresh(session, provider=provider, record=record)
        return record

    probe_model = _pick_probe_model(provider, cfg)
    if not probe_model:
        finished_at = datetime.now(UTC)
        record = ProviderTestRecord(
            provider_uuid=provider.id,
            mode=mode,
            success=False,
            summary="probe model missing",
            probe_results=[
                {
                    "case": "probe",
                    "mode": mode,
                    "model": None,
                    "input": effective_prompt,
                    "status": "probe_model_missing",
                    "latency_ms": None,
                    "timestamp": finished_at.isoformat(),
                }
            ],
            latency_ms=None,
            error_code="probe_model_missing",
            cost=0.0,
            started_at=started_at,
            finished_at=finished_at,
        )
        repo_persist_provider_test_record(session, record=record)
        _record_audit_log(
            session,
            provider,
            "test",
            operator_id=operator_id,
            remark=remark,
            from_status=previous_status,
            to_status=provider.audit_status,
            test_record=record,
        )
        repo_commit_refresh(session, provider=provider, record=record)
        return record

    async def _run_probe():
        redis = get_redis_client()
        async with CurlCffiClient(
            timeout=settings.upstream_timeout,
            impersonate="chrome120",
            trust_env=True,
        ) as client:
            result = await execute_user_probe(
                client,  # CurlCffiClient 与 httpx.AsyncClient 接口兼容
                provider_cfg=cfg,
                model_id=probe_model,
                prompt=effective_prompt,
                max_tokens=32,
                api_style="auto",
                redis=redis,
            )

            finished_at = datetime.now(UTC)
            status = HealthStatus(
                provider_id=provider.provider_id,
                status=_status_from_probe_result(
                    success=result.success, status_code=result.status_code
                ),
                timestamp=finished_at.timestamp(),
                response_time_ms=float(result.latency_ms) if result.latency_ms is not None else None,
                error_message=result.error_message,
                last_successful_check=finished_at.timestamp() if result.success else None,
            )
            await persist_provider_health(
                redis,
                session,
                provider,
                status,
                cache_ttl_seconds=settings.provider_health_cache_ttl_seconds,
            )
            return status, result

    try:
        probe_status, probe_result = anyio.run(_run_probe)
        latency_ms = int(probe_result.latency_ms) if probe_result.latency_ms is not None else None
        if probe_result.success:
            error_code = None
        else:
            error_code = probe_result.error_message or (
                f"HTTP {probe_result.status_code}" if probe_result.status_code else "probe_failed"
            )
    except Exception as exc:  # pragma: no cover - 网络/上游异常
        logger.exception("Provider %s test failed: %s", provider_id, exc)
        probe_status = None
        latency_ms = None
        error_code = "probe_failed"
        provider.audit_status = "testing"

    finished_at = datetime.now(UTC)
    record = ProviderTestRecord(
        provider_uuid=provider.id,
        mode=mode,
        success=error_code is None,
        summary=remark or (probe_status.status.value if probe_status else "probe failed"),
        probe_results=[
            {
                "case": "probe",
                "mode": mode,
                "model": probe_model,
                "input": effective_prompt,
                "status": probe_status.status.value if probe_status else "error",
                "latency_ms": latency_ms,
                "timestamp": finished_at.isoformat(),
            }
        ],
        latency_ms=latency_ms,
        error_code=error_code,
        cost=0.0,
        started_at=started_at,
        finished_at=finished_at,
    )
    repo_persist_provider_test_record(session, record=record)
    _record_audit_log(
        session,
        provider,
        "test",
        operator_id=operator_id,
        remark=remark,
        from_status=previous_status,
        to_status=provider.audit_status,
        test_record=record,
    )
    repo_commit_refresh(session, provider=provider, record=record)
    logger.info("Provider %s test recorded (mode=%s)", provider_id, mode)
    return record


def approve_provider(
    session: Session,
    provider_id: str,
    operator_id: UUID | None,
    *,
    remark: str | None = None,
    limited: bool = False,
    limit_qps: int | None = None,
) -> Provider:
    provider = _get_provider(session, provider_id)
    previous_status = provider.audit_status
    provider.audit_status = "approved_limited" if limited else "approved"
    provider.operation_status = "active"
    if limited and limit_qps:
        provider.max_qps = limit_qps

    _record_audit_log(
        session,
        provider,
        "approve_limited" if limited else "approve",
        operator_id=operator_id,
        remark=remark,
        from_status=previous_status,
        to_status=provider.audit_status,
    )
    repo_commit_refresh(session, provider=provider, record=None)
    return provider


def reject_provider(
    session: Session,
    provider_id: str,
    operator_id: UUID | None,
    *,
    remark: str | None = None,
) -> Provider:
    provider = _get_provider(session, provider_id)
    previous_status = provider.audit_status
    provider.audit_status = "rejected"
    provider.operation_status = "offline"
    _record_audit_log(
        session,
        provider,
        "reject",
        operator_id=operator_id,
        remark=remark,
        from_status=previous_status,
        to_status=provider.audit_status,
    )
    repo_commit_refresh(session, provider=provider, record=None)
    return provider


def update_operation_status(
    session: Session,
    provider_id: str,
    operator_id: UUID | None,
    new_status: Literal["active", "paused", "offline"],
    *,
    remark: str | None = None,
) -> Provider:
    if new_status not in OPERATION_STATES:
        raise ProviderAuditError(f"Invalid operation status: {new_status}")

    provider = _get_provider(session, provider_id)
    previous_status = provider.operation_status
    provider.operation_status = new_status
    _record_audit_log(
        session,
        provider,
        f"operation_{new_status}",
        operator_id=operator_id,
        remark=remark,
        operation_from_status=previous_status,
        operation_to_status=new_status,
    )
    repo_commit_refresh(session, provider=provider, record=None)
    return provider


def get_latest_test_record(
    session: Session, provider_uuid: UUID
) -> ProviderTestRecord | None:
    return repo_get_latest_test_record(session, provider_uuid=provider_uuid)


def list_test_records(
    session: Session, provider_id: str, limit: int = 20
) -> list[ProviderTestRecord]:
    provider = _get_provider(session, provider_id)
    return repo_list_test_records(session, provider_uuid=provider.id, limit=limit)


def list_audit_logs(
    session: Session, provider_id: str, limit: int = 50
) -> list[ProviderAuditLog]:
    provider = _get_provider(session, provider_id)
    return repo_list_audit_logs(session, provider_uuid=provider.id, limit=limit)


__all__ = [
    "ProviderAuditError",
    "ProviderNotFoundError",
    "approve_provider",
    "get_latest_test_record",
    "reject_provider",
    "trigger_provider_test",
    "update_operation_status",
]
