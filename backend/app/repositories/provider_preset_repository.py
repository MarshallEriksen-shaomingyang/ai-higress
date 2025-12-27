from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ProviderPreset


def list_provider_presets(db: Session) -> list[ProviderPreset]:
    stmt: Select[tuple[ProviderPreset]] = select(ProviderPreset).order_by(
        ProviderPreset.created_at.desc()
    )
    return list(db.execute(stmt).scalars().all())


def get_provider_preset(db: Session, *, preset_id: str) -> ProviderPreset | None:
    stmt: Select[tuple[ProviderPreset]] = select(ProviderPreset).where(
        ProviderPreset.preset_id == preset_id
    )
    return db.execute(stmt).scalars().first()


def create_provider_preset(db: Session, *, preset: ProviderPreset) -> ProviderPreset:
    db.add(preset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(preset)
    return preset


def persist_provider_preset(db: Session, *, preset: ProviderPreset) -> ProviderPreset:
    db.add(preset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(preset)
    return preset


def delete_provider_preset(db: Session, *, preset: ProviderPreset) -> None:
    db.delete(preset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def rollback(db: Session) -> None:
    db.rollback()


__all__ = [
    "create_provider_preset",
    "delete_provider_preset",
    "get_provider_preset",
    "list_provider_presets",
    "persist_provider_preset",
    "rollback",
]
