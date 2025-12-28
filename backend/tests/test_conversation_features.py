from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import APIKey, User
from app.services import chat_history_service
from tests.utils import jwt_auth_headers


def test_conversation_features(client: TestClient, db_session: Session):
    # 1. Setup: User, APIKey, Assistant
    user = User(email="test@example.com", username="testuser", hashed_password="...")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    api_key = APIKey(user_id=user.id, name="test-key", key_prefix="test", key_hash="...")
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)

    project_id = api_key.id
    user_id = user.id
    headers = jwt_auth_headers(str(user_id))

    assistant = chat_history_service.create_assistant(
        db_session,
        user_id=user_id,
        project_id=project_id,
        name="Test Bot",
        system_prompt="...",
        default_logical_model="gpt-4",
        model_preset={}
    )
    assert assistant.title_logical_model is None
    assistant_id = assistant.id

    # 2. Create 3 conversations
    c1 = chat_history_service.create_conversation(db_session, user_id=user_id, project_id=project_id, assistant_id=assistant_id, title="Chat 1")
    c2 = chat_history_service.create_conversation(db_session, user_id=user_id, project_id=project_id, assistant_id=assistant_id, title="Chat 2")
    c3 = chat_history_service.create_conversation(db_session, user_id=user_id, project_id=project_id, assistant_id=assistant_id, title="Chat 3")

    # Initially order is c3, c2, c1 (by last_activity_at desc)
    resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
    items = resp.json()["items"]
    assert items[0]["title"] == "Chat 3"
    assert items[0]["is_pinned"] is False
    assert items[0]["unread_count"] == 0

    # 3. Pin c1
    resp = client.put(f"/v1/conversations/{c1.id}", headers=headers, json={"is_pinned": True})
    assert resp.status_code == 200
    assert resp.json()["is_pinned"] is True

    # Now order should be c1 (pinned), then c3, c2
    resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
    items = resp.json()["items"]
    assert items[0]["title"] == "Chat 1"
    assert items[0]["is_pinned"] is True
    assert items[1]["title"] == "Chat 3"

    # 4. Test preview and unread count
    # User message
    msg = chat_history_service.create_user_message(db_session, conversation=c1, content_text="Hello Bot")
    db_session.refresh(c1)
    assert c1.last_message_content == "Hello Bot"

    # Assistant message (updates unread)
    chat_history_service.create_assistant_message_after_user(
        db_session,
        conversation_id=c1.id,
        user_sequence=msg.sequence,
        content_text="Hello Human"
    )
    db_session.refresh(c1)
    assert c1.last_message_content == "Hello Human"
    assert c1.unread_count == 1

    # Check in list API
    resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
    item = [i for i in resp.json()["items"] if i["conversation_id"] == str(c1.id)][0]
    assert item["last_message_content"] == "Hello Human"
    assert item["unread_count"] == 1

    # 5. List messages (should reset unread count)
    resp = client.get(f"/v1/conversations/{c1.id}/messages", headers=headers)
    assert resp.status_code == 200

    db_session.refresh(c1)
    assert c1.unread_count == 0

    resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
    item = [i for i in resp.json()["items"] if i["conversation_id"] == str(c1.id)][0]
    assert item["unread_count"] == 0

    # 6. Summary is user-visible and editable via conversation update
    resp = client.put(f"/v1/conversations/{c1.id}", headers=headers, json={"summary": "SUM"})
    assert resp.status_code == 200
    assert resp.json()["summary_text"] == "SUM"
    assert resp.json()["summary_until_sequence"] == 2

    resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
    item = [i for i in resp.json()["items"] if i["conversation_id"] == str(c1.id)][0]
    assert item["summary_text"] == "SUM"

    resp = client.put(f"/v1/conversations/{c1.id}", headers=headers, json={"summary": None})
    assert resp.status_code == 200
    assert resp.json()["summary_text"] is None
    assert resp.json()["summary_until_sequence"] == 0
