from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from tests.utils import jwt_auth_headers


def test_list_conversations_archived(client: TestClient, db_session: Session):
    # 1. Get the seeded user
    user = db_session.execute(select(User).where(User.email == "admin@example.com")).scalars().first()
    assert user is not None
    user_id = str(user.id)
    headers = jwt_auth_headers(user_id)

    # 2. Create Project (implicit in API Key if needed, but here we create assistant with project_id)
    # Actually, assistants need a project_id (UUID). The seeded API Key has one?
    # Let's check seed_user_and_key in utils.py. APIKey model has 'id' which acts as project_id usually.
    # The APIKey table is used as "Project".
    # We can get the API Key ID.
    from app.models import APIKey
    api_key = db_session.execute(select(APIKey).where(APIKey.user_id == user.id)).scalars().first()
    project_id = str(api_key.id)

    # 0. Invalid project_id should return 404 (avoid misleading "name exists" or 500).
    resp = client.post(
        "/v1/assistants",
        headers=headers,
        json={
            "project_id": user_id,  # user_id != api_key_id
            "name": "Should Fail",
            "system_prompt": "You are a test bot.",
            "default_logical_model": "gpt-4o",
            "model_preset": {},
        },
    )
    assert resp.status_code == 404, resp.text
    detail = resp.json().get("detail") or {}
    assert detail.get("error") == "not_found"

    # 3. Create Assistant
    resp = client.post(
        "/v1/assistants",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "Test Assistant",
            "system_prompt": "You are a test bot.",
            "default_logical_model": "gpt-4o",
            "model_preset": {},
        },
    )
    assert resp.status_code == 201, resp.text
    assistant_id = resp.json()["assistant_id"]

    # 4. Create Active Conversation
    resp = client.post(
        "/v1/conversations",
        headers=headers,
        json={
            "project_id": project_id,
            "assistant_id": assistant_id,
            "title": "Active Chat",
        },
    )
    assert resp.status_code == 201
    active_payload = resp.json()
    active_id = active_payload["conversation_id"]
    assert "archived_at" in active_payload
    assert active_payload["archived_at"] is None

    # 5. Create Another Conversation and Archive it
    resp = client.post(
        "/v1/conversations",
        headers=headers,
        json={
            "project_id": project_id,
            "assistant_id": assistant_id,
            "title": "Archived Chat",
        },
    )
    assert resp.status_code == 201
    archived_payload = resp.json()
    archived_id = archived_payload["conversation_id"]
    assert "archived_at" in archived_payload
    assert archived_payload["archived_at"] is None

    # Archive it
    resp = client.put(
        f"/v1/conversations/{archived_id}",
        headers=headers,
        json={"title": "Archived Chat", "archived": True},
    )
    assert resp.status_code == 200
    updated_payload = resp.json()
    assert updated_payload["conversation_id"] == archived_id
    assert updated_payload["archived_at"] is not None

    # 6. List Default (Active only, archived=False)
    resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["conversation_id"] for i in items]
    assert active_id in ids
    assert archived_id not in ids
    active_item = next(i for i in items if i["conversation_id"] == active_id)
    assert "archived_at" in active_item
    assert active_item["archived_at"] is None

    # 7. List Archived (archived=True)
    resp = client.get(
        f"/v1/conversations?assistant_id={assistant_id}&archived=true", headers=headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["conversation_id"] for i in items]
    assert active_id not in ids
    assert archived_id in ids
    archived_item = next(i for i in items if i["conversation_id"] == archived_id)
    assert "archived_at" in archived_item
    assert archived_item["archived_at"] is not None
