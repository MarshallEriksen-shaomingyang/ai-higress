from __future__ import annotations

"""
Shared pytest configuration.

This file ensures the project root is on sys.path so that `import app`
works consistently in all tests, and provides reusable fixtures for tests.
"""

import sys
from pathlib import Path

# Ensure project root is importable for test modules.
# This MUST be done before importing app modules.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.routes import create_app
from tests.utils import auth_headers, install_inmemory_db


@pytest.fixture()
def app_with_inmemory_db() -> tuple[FastAPI, sessionmaker[Session]]:
    fastapi_app = create_app()
    SessionLocal: sessionmaker[Session] = install_inmemory_db(fastapi_app)

    # Patch app.routes.SessionLocal to use in-memory DB during lifespan
    import app.routes
    original_session_local = app.routes.SessionLocal
    app.routes.SessionLocal = SessionLocal

    try:
        yield fastapi_app, SessionLocal
    finally:
        app.routes.SessionLocal = original_session_local


@pytest.fixture()
def client(app_with_inmemory_db):
    app, _ = app_with_inmemory_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(app_with_inmemory_db):
    _, SessionLocal = app_with_inmemory_db
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def api_key_auth_header():
    return auth_headers("timeline")
