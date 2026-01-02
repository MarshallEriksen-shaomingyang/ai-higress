from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import KBAttribute


_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,159}$")


def make_subject_id(*, scope: str, user_id: UUID | None = None, project_id: UUID | None = None) -> str:
    scope_norm = str(scope or "").strip().lower()
    if scope_norm == "user":
        if user_id is None:
            raise ValueError("user_id is required for scope=user")
        return f"user:{UUID(str(user_id))}"
    if scope_norm == "project":
        if project_id is None:
            raise ValueError("project_id is required for scope=project")
        return f"project:{UUID(str(project_id))}"
    if scope_norm == "system":
        return "system:global"
    raise ValueError(f"unsupported scope: {scope}")


def list_attributes(
    db: Session,
    *,
    subject_id: str,
    category: str | None = None,
    limit: int = 200,
) -> list[KBAttribute]:
    sid = str(subject_id or "").strip()
    if not sid:
        return []
    stmt: Select[tuple[KBAttribute]] = select(KBAttribute).where(KBAttribute.subject_id == sid)
    if category:
        stmt = stmt.where(KBAttribute.category == str(category))
    stmt = stmt.order_by(KBAttribute.key.asc())
    safe_limit = max(1, min(int(limit or 0), 500))
    stmt = stmt.limit(safe_limit)
    return list(db.execute(stmt).scalars().all())


def upsert_attribute(
    db: Session,
    *,
    subject_id: str,
    scope: str,
    category: str,
    key: str,
    value: Any,
    owner_user_id: UUID | None = None,
    project_id: UUID | None = None,
    confidence: float | None = None,
    source_conversation_id: UUID | None = None,
    source_until_sequence: int | None = None,
) -> KBAttribute:
    sid = str(subject_id or "").strip()
    if not sid:
        raise ValueError("subject_id is required")

    key_norm = str(key or "").strip()
    if not key_norm or not _KEY_RE.match(key_norm):
        raise ValueError("invalid key")

    scope_norm = str(scope or "").strip().lower()
    if scope_norm not in {"user", "project", "system"}:
        raise ValueError("invalid scope")
    category_norm = str(category or "").strip().lower()
    if category_norm not in {"preference", "constraint", "config"}:
        category_norm = "config"

    existing = db.execute(
        select(KBAttribute).where(KBAttribute.subject_id == sid, KBAttribute.key == key_norm)
    ).scalars().first()
    if existing is not None:
        existing.scope = scope_norm
        existing.category = category_norm
        existing.value = value
        existing.owner_user_id = owner_user_id
        existing.project_id = project_id
        existing.confidence = confidence
        existing.source_conversation_id = source_conversation_id
        existing.source_until_sequence = source_until_sequence
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    row = KBAttribute(
        subject_id=sid,
        scope=scope_norm,
        category=category_norm,
        key=key_norm,
        value=value,
        owner_user_id=owner_user_id,
        project_id=project_id,
        confidence=confidence,
        source_conversation_id=source_conversation_id,
        source_until_sequence=source_until_sequence,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent insert: retry as update.
        return upsert_attribute(
            db,
            subject_id=sid,
            scope=scope_norm,
            category=category_norm,
            key=key_norm,
            value=value,
            owner_user_id=owner_user_id,
            project_id=project_id,
            confidence=confidence,
            source_conversation_id=source_conversation_id,
            source_until_sequence=source_until_sequence,
        )
    db.refresh(row)
    return row


__all__ = ["list_attributes", "make_subject_id", "upsert_attribute"]

