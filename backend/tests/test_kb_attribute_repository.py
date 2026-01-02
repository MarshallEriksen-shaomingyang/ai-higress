from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import User
from app.repositories.kb_attribute_repository import list_attributes, make_subject_id, upsert_attribute


def test_make_subject_id_user() -> None:
    sid = make_subject_id(scope="user", user_id=UUID("00000000-0000-0000-0000-000000000001"))
    assert sid == "user:00000000-0000-0000-0000-000000000001"


def test_make_subject_id_project() -> None:
    sid = make_subject_id(scope="project", project_id=UUID("00000000-0000-0000-0000-0000000000aa"))
    assert sid == "project:00000000-0000-0000-0000-0000000000aa"


def test_upsert_attribute_inserts_and_updates(db_session) -> None:
    user_id = db_session.execute(select(User.id)).scalar_one()
    sid = make_subject_id(scope="user", user_id=user_id)

    row1 = upsert_attribute(
        db_session,
        subject_id=sid,
        scope="user",
        category="preference",
        key="response.style",
        value="concise",
        owner_user_id=user_id,
    )
    assert row1.key == "response.style"
    assert row1.value == "concise"

    row2 = upsert_attribute(
        db_session,
        subject_id=sid,
        scope="user",
        category="preference",
        key="response.style",
        value="verbose",
        owner_user_id=user_id,
    )
    assert row2.id == row1.id
    assert row2.value == "verbose"

    rows = list_attributes(db_session, subject_id=sid)
    assert len(rows) == 1
    assert rows[0].value == "verbose"


def test_upsert_attribute_rejects_invalid_key(db_session) -> None:
    with pytest.raises(ValueError):
        upsert_attribute(
            db_session,
            subject_id="user:00000000-0000-0000-0000-000000000001",
            scope="user",
            category="preference",
            key="not a key",
            value="x",
        )
