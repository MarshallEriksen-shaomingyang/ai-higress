from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Provider, ProviderAuditLog, ProviderTestRecord


def get_provider_by_provider_id(db: Session, *, provider_id: str) -> Provider | None:
    stmt: Select[tuple[Provider]] = select(Provider).where(Provider.provider_id == provider_id)
    return db.execute(stmt).scalars().first()


def persist_provider_audit_log(db: Session, *, log: ProviderAuditLog) -> ProviderAuditLog:
    db.add(log)
    return log


def persist_provider_test_record(db: Session, *, record: ProviderTestRecord) -> ProviderTestRecord:
    db.add(record)
    return record


def commit_refresh(db: Session, *, provider: Provider | None = None, record: ProviderTestRecord | None = None) -> None:
    db.commit()
    if record is not None:
        db.refresh(record)
    if provider is not None:
        db.refresh(provider)


def list_test_records(db: Session, *, provider_uuid: object, limit: int) -> list[ProviderTestRecord]:
    stmt: Select[tuple[ProviderTestRecord]] = (
        select(ProviderTestRecord)
        .where(ProviderTestRecord.provider_uuid == provider_uuid)
        .order_by(ProviderTestRecord.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_latest_test_record(db: Session, *, provider_uuid: object) -> ProviderTestRecord | None:
    stmt: Select[tuple[ProviderTestRecord]] = (
        select(ProviderTestRecord)
        .where(ProviderTestRecord.provider_uuid == provider_uuid)
        .order_by(ProviderTestRecord.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def list_audit_logs(db: Session, *, provider_uuid: object, limit: int) -> list[ProviderAuditLog]:
    stmt: Select[tuple[ProviderAuditLog]] = (
        select(ProviderAuditLog)
        .where(ProviderAuditLog.provider_uuid == provider_uuid)
        .order_by(ProviderAuditLog.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


__all__ = [
    "commit_refresh",
    "get_latest_test_record",
    "get_provider_by_provider_id",
    "list_audit_logs",
    "list_test_records",
    "persist_provider_audit_log",
    "persist_provider_test_record",
]

