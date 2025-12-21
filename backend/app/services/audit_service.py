import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.logging_config import logger
from app.services.compliance_service import ContentFinding, findings_to_summary


def _to_str(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


def record_audit_event(
    *,
    action: str,
    stage: str,
    user_id: UUID | str | None,
    api_key_id: UUID | str | None,
    logical_model: str | None,
    provider_id: str | None,
    session_id: str | None,
    status_code: int | None = None,
    decision: str | None = None,
    findings: list[ContentFinding] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    写入结构化审计日志，便于后期接入集中日志/合规系统。
    """
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "action": action,
        "stage": stage,
        "user_id": _to_str(user_id),
        "api_key_id": _to_str(api_key_id),
        "logical_model": logical_model,
        "provider_id": provider_id,
        "session_id": session_id,
        "status_code": status_code,
        "decision": decision,
        "findings": findings_to_summary(findings or []),
        "metadata": metadata or {},
    }
    try:
        logger.info("AUDIT %s", json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.exception("Failed to record audit event: %s", payload)
