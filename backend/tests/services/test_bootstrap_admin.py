from __future__ import annotations

import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import APIKey, Base, User
from app.services.bootstrap_admin import ensure_initial_admin
from app.settings import settings


def _build_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine, SessionLocal


def test_ensure_initial_admin_creates_user_without_key(caplog):
    engine, SessionLocal = _build_session_factory()
    caplog.set_level(logging.WARNING)
    try:
        with SessionLocal() as session:
            result = ensure_initial_admin(session)
            assert result is not None
            assert result.username == settings.default_admin_username
            assert result.password

        with SessionLocal() as session:
            user_count = session.execute(select(User)).scalars().all()
            assert len(user_count) == 1
            key_count = session.execute(select(APIKey)).scalars().all()
            assert len(key_count) == 0
        assert "已自动创建初始管理员账号" in caplog.text
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_ensure_initial_admin_is_idempotent():
    engine, SessionLocal = _build_session_factory()
    try:
        with SessionLocal() as session:
            ensure_initial_admin(session)
        with SessionLocal() as session:
            result = ensure_initial_admin(session)
            assert result is None
            users = session.execute(select(User)).scalars().all()
            assert len(users) == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
