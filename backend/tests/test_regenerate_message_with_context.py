from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssistantPreset, Conversation, Message, Run, User
from app.services.bridge_gateway_client import BridgeGatewayClient
from tests.utils import jwt_auth_headers


@pytest.mark.asyncio
async def test_regenerate_message_accepts_context_and_injects_tools(
    client,
    db_session: Session,
    monkeypatch,
):
    user = db_session.execute(select(User)).scalars().first()
    assert user is not None

    # Create assistant + conversation.
    api_key_id = user.api_keys[0].id  # seeded in install_inmemory_db
    assistant = AssistantPreset(
        user_id=user.id,
        api_key_id=api_key_id,
        name="a1",
        system_prompt="",
        default_logical_model="gpt-4.1",
        title_logical_model=None,
        model_preset=None,
        archived_at=None,
    )
    db_session.add(assistant)
    db_session.flush()

    conv = Conversation(
        user_id=user.id,
        api_key_id=api_key_id,
        assistant_id=assistant.id,
        title=None,
        last_activity_at=datetime.now(UTC),
        archived_at=None,
        is_pinned=False,
        last_message_content=None,
        unread_count=0,
    )
    db_session.add(conv)
    db_session.flush()

    user_msg = Message(conversation_id=conv.id, role="user", content={"text": "hi"}, sequence=1)
    assistant_msg = Message(conversation_id=conv.id, role="assistant", content={"text": "old"}, sequence=2)
    db_session.add_all([user_msg, assistant_msg])
    db_session.flush()

    # Seed a previous run for model fallback.
    last_run = Run(
        message_id=user_msg.id,
        user_id=user.id,
        api_key_id=api_key_id,
        requested_logical_model="gpt-4.1",
        selected_provider_id=None,
        selected_provider_model=None,
        status="succeeded",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        latency_ms=1,
        cost_credits=0,
        error_code=None,
        error_message=None,
        request_payload={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hi"}]},
        response_payload={"choices": [{"message": {"content": "old"}}]},
        output_text="old",
        output_preview="old",
    )
    db_session.add(last_run)
    db_session.commit()

    async def _stub_list_tools(self, agent_id: str) -> dict:
        assert agent_id == "agent-1"
        return {
            "tools": [
                {
                    "name": "search",
                    "description": "",
                    "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
                }
            ]
        }

    monkeypatch.setattr(BridgeGatewayClient, "list_tools", _stub_list_tools)

    captured: dict = {}

    async def _stub_execute_run_non_stream(*args, **kwargs):
        captured["payload_override"] = kwargs.get("payload_override")
        run = kwargs["run"]
        run.status = "succeeded"
        run.output_text = "ok"
        run.output_preview = "ok"
        run.response_payload = {"choices": [{"message": {"content": "ok"}}]}
        return run

    async def _stub_invoke_and_wait(*args, **kwargs):
        # Should not actually be called in this test because the stubbed model never returns tool_calls.
        raise AssertionError("tool invoke should not be called")

    monkeypatch.setattr("app.services.chat_app_service.execute_run_non_stream", _stub_execute_run_non_stream)
    monkeypatch.setattr("app.services.chat_app_service.invoke_bridge_tool_and_wait", _stub_invoke_and_wait)

    resp = client.post(
        f"/v1/messages/{assistant_msg.id}/regenerate",
        headers=jwt_auth_headers(str(user.id)),
        json={
            "override_logical_model": "gpt-4.1",
            "model_preset": {"temperature": 0.2},
            "bridge_agent_ids": ["agent-1"],
            "bridge_tool_selections": [{"agent_id": "agent-1", "tool_names": ["search"]}],
        },
    )
    assert resp.status_code == 200, resp.text

    payload = captured.get("payload_override")
    assert isinstance(payload, dict)
    assert payload.get("model") == "gpt-4.1"
    assert payload.get("temperature") == 0.2
    assert payload.get("tool_choice") == "auto"
    assert isinstance(payload.get("tools"), list) and len(payload["tools"]) == 1

