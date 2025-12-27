from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import ProjectEvalConfig


def get_project_eval_config(db: Session, *, project_id: object) -> ProjectEvalConfig | None:
    stmt: Select[tuple[ProjectEvalConfig]] = select(ProjectEvalConfig).where(
        ProjectEvalConfig.api_key_id == project_id
    )
    return db.execute(stmt).scalars().first()


def persist_project_eval_config(db: Session, *, cfg: ProjectEvalConfig) -> ProjectEvalConfig:
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


__all__ = [
    "get_project_eval_config",
    "persist_project_eval_config",
]

