from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import APIKey, User
from app.services import chat_history_service
from app.services.chat_run_service import build_openai_request_payload
from app.settings import settings
from tests.utils import jwt_auth_headers


def test_chat_context_window_limits_upstream_payload_messages(
    client: TestClient, db_session: Session
):
    user = User(email="context-window@example.com", username="context-window", hashed_password="...")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    api_key = APIKey(user_id=user.id, name="test-key", key_prefix="test", key_hash="...")
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)

    # ensure JWT dependency would accept the user in real endpoints
    _ = jwt_auth_headers(str(user.id))

    assistant = chat_history_service.create_assistant(
        db_session,
        user_id=user.id,
        project_id=api_key.id,
        name="Test Assistant",
        system_prompt="SYS",
        default_logical_model="gpt-4o",
        title_logical_model=None,
        model_preset={},
    )

    conversation = chat_history_service.create_conversation(
        db_session,
        user_id=user.id,
        project_id=api_key.id,
        assistant_id=assistant.id,
        title="Chat",
    )

    # 3 full turns
    u1 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u1")
    chat_history_service.create_assistant_message_after_user(
        db_session, conversation_id=conversation.id, user_sequence=u1.sequence, content_text="a1"
    )
    u2 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u2")
    chat_history_service.create_assistant_message_after_user(
        db_session, conversation_id=conversation.id, user_sequence=u2.sequence, content_text="a2"
    )
    u3 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u3")
    chat_history_service.create_assistant_message_after_user(
        db_session, conversation_id=conversation.id, user_sequence=u3.sequence, content_text="a3"
    )

    # new user message (this is new_user_message)
    u4 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u4")

    original = settings.chat_context_max_messages
    settings.chat_context_max_messages = 2
    try:
        payload = build_openai_request_payload(
            db_session,
            conversation=conversation,
            assistant=assistant,
            user_message=u4,
            requested_logical_model="gpt-4o",
            model_preset_override=None,
        )
    finally:
        settings.chat_context_max_messages = original

    assert payload["model"] == "gpt-4o"
    assert payload["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
        {"role": "user", "content": "u4"},
    ]


def test_chat_context_window_injects_summary_and_resets_history(
    client: TestClient, db_session: Session
):
    user = User(email="summary-window@example.com", username="summary-window", hashed_password="...")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    api_key = APIKey(user_id=user.id, name="test-key", key_prefix="test", key_hash="...")
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)

    _ = jwt_auth_headers(str(user.id))

    assistant = chat_history_service.create_assistant(
        db_session,
        user_id=user.id,
        project_id=api_key.id,
        name="Test Assistant",
        system_prompt="SYS",
        default_logical_model="gpt-4o",
        title_logical_model=None,
        model_preset={},
    )

    conversation = chat_history_service.create_conversation(
        db_session,
        user_id=user.id,
        project_id=api_key.id,
        assistant_id=assistant.id,
        title="Chat",
    )

    u1 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u1")
    chat_history_service.create_assistant_message_after_user(
        db_session, conversation_id=conversation.id, user_sequence=u1.sequence, content_text="a1"
    )
    u2 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u2")
    chat_history_service.create_assistant_message_after_user(
        db_session, conversation_id=conversation.id, user_sequence=u2.sequence, content_text="a2"
    )
    u3 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u3")
    a3 = chat_history_service.create_assistant_message_after_user(
        db_session, conversation_id=conversation.id, user_sequence=u3.sequence, content_text="a3"
    )

    conversation.summary_text = "SUM"
    conversation.summary_until_sequence = int(a3.sequence or 0)
    db_session.add(conversation)
    db_session.commit()

    u4 = chat_history_service.create_user_message(db_session, conversation=conversation, content_text="u4")

    original = settings.chat_context_max_messages
    settings.chat_context_max_messages = 50
    try:
        payload = build_openai_request_payload(
            db_session,
            conversation=conversation,
            assistant=assistant,
            user_message=u4,
            requested_logical_model="gpt-4o",
            model_preset_override=None,
        )
    finally:
        settings.chat_context_max_messages = original

    assert payload["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "system", "content": "Conversation summary:\nSUM"},
        {"role": "user", "content": "u4"},
    ]
