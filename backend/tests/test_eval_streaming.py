from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.deps import get_db
from app.jwt_auth import AuthenticatedUser
from app.models import Eval, Message, Run
from main import app


@pytest.fixture
def mock_user():
    return AuthenticatedUser(
        id=str(uuid4()),
        username="testuser",
        email="test@example.com",
        is_superuser=False,
        is_active=True
    )

@pytest.mark.asyncio
async def test_create_eval_streaming_flow():
    eval_id = uuid4()
    baseline_run_id = uuid4()
    challenger_run_id = uuid4()
    message_id = uuid4()

    mock_eval = MagicMock(spec=Eval)
    mock_eval.id = eval_id
    mock_eval.baseline_run_id = baseline_run_id
    mock_eval.status = "running"
    mock_eval.challenger_run_ids = [str(challenger_run_id)]
    mock_eval.created_at = None
    mock_eval.updated_at = None

    mock_run = MagicMock(spec=Run)
    mock_run.id = challenger_run_id
    mock_run.requested_logical_model = "gpt-4-test"
    mock_run.status = "queued"
    mock_run.output_preview = None
    mock_run.latency_ms = None
    mock_run.error_code = None
    mock_run.request_payload = {"messages": []}

    mock_user_message = MagicMock(spec=Message)
    mock_user_message.id = message_id

    mock_db_session = MagicMock()
    mock_db_session.__enter__.return_value = mock_db_session

    # We use a side_effect that returns appropriate objects based on what's being fetched
    def mock_first_side_effect():
        # This is a bit hacky but allows multiple calls to .scalars().first()
        # The order in _run_task: task_run, (get_conv), (get_asst), user_message
        # In endpoint: user_message (actually it is not used in endpoint main db anymore in my latest refactor, oh wait, it is used in create_eval)
        # Wait, create_eval is patched, so it doesn't call first().
        # So we only have calls in _run_task.
        yield mock_run          # task_run
        yield mock_user_message # user_message
        while True:
            yield None

    first_gen = mock_first_side_effect()
    mock_db_session.execute.return_value.scalars.return_value.first.side_effect = lambda: next(first_gen)

    with patch("app.api.v1.eval_routes.create_eval", new_callable=AsyncMock) as mock_create_eval, \
         patch("app.api.v1.eval_routes.execute_run_stream") as mock_execute_run_stream, \
         patch("app.api.v1.eval_routes.resolve_project_context") as mock_resolve_ctx, \
         patch("app.api.v1.eval_routes.get_or_default_project_eval_config") as mock_get_cfg, \
         patch("app.api.v1.eval_routes.get_effective_provider_ids_for_user") as mock_get_pids, \
         patch("app.api.v1.eval_routes._to_authenticated_api_key") as mock_to_auth, \
         patch("app.api.v1.eval_routes.get_conversation") as mock_get_conv, \
         patch("app.api.v1.eval_routes.get_assistant") as mock_get_asst, \
         patch("app.api.v1.eval_routes._maybe_mark_eval_ready") as mock_mark_ready, \
         patch("app.api.v1.eval_routes.SessionLocal") as mock_session_local:

        mock_create_eval.return_value = (mock_eval, [mock_run], {"summary": "test"})
        mock_session_local.return_value = mock_db_session

        async def mock_stream_iter(*args, **kwargs):
            yield {"run_id": str(challenger_run_id), "type": "run.delta", "status": "running", "delta": "Hello"}
            yield {"run_id": str(challenger_run_id), "type": "run.completed", "status": "succeeded", "full_text": "Hello world"}

        mock_execute_run_stream.side_effect = mock_stream_iter

        mock_resolve_ctx.return_value = MagicMock(project_id=uuid4(), api_key=MagicMock())
        mock_get_cfg.return_value = MagicMock(provider_scopes=None)
        mock_get_pids.return_value = {"openai"}
        mock_to_auth.return_value = MagicMock()
        mock_get_conv.return_value = MagicMock()
        mock_get_asst.return_value = MagicMock()

        app.dependency_overrides[get_db] = lambda: mock_db_session
        from app.jwt_auth import require_jwt_token
        app.dependency_overrides[require_jwt_token] = lambda: AuthenticatedUser(
            id=str(uuid4()),
            username="admin",
            email="admin@example.com",
            is_superuser=True,
            is_active=True
        )

        client_instance = TestClient(app)
        payload = {
            "project_id": str(uuid4()),
            "assistant_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "message_id": str(message_id),
            "baseline_run_id": str(baseline_run_id),
            "streaming": True
        }

        with client_instance.stream("POST", "/v1/evals", json=payload) as response:
            assert response.status_code == 200
            events = []

            for line in response.iter_lines():
                if not line: continue
                if isinstance(line, bytes):
                    line_str = line.decode("utf-8")
                else:
                    line_str = line

                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]": continue
                    data = json.loads(data_str)
                    events.append(data)

            # Check for specific event types
            event_types = [e["type"] for e in events]
            assert "eval.created" in event_types
            assert "run.delta" in event_types
            assert "run.completed" in event_types
            assert "eval.completed" in event_types

            # Verify run_id in run.delta
            delta_event = next(e for e in events if e["type"] == "run.delta")
            assert delta_event["run_id"] == str(challenger_run_id)


    app.dependency_overrides.clear()
