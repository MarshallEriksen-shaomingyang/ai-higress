from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.deps import get_http_client, get_redis
from app.routes import create_app
from app.schemas import LogicalModel, ModelCapability, PhysicalModel, ProviderConfig
from app.settings import settings
from app.storage.redis_service import LOGICAL_MODEL_KEY_TEMPLATE
from tests.utils import InMemoryRedis, install_inmemory_db, jwt_auth_headers


def _mock_send(request: httpx.Request) -> httpx.Response:
    if request.method == "POST" and request.url.path.endswith("/v1/chat/completions"):
        body = json.loads(request.content.decode("utf-8"))
        system_text = ""
        for m in body.get("messages", []) or []:
            if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str):
                system_text = m["content"]
                break

        if "上下文特征" in system_text and "risk_tier" in system_text:
            data = {
                "id": "cmpl-test",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"task_type":"qa","risk_tier":"low"}'},
                        "finish_reason": "stop",
                    }
                ],
            }
            return httpx.Response(200, json=data)

        if "为什么系统选择这些 challenger" in system_text:
            data = {
                "id": "cmpl-test",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"summary":"基于探索与样本数选择候选进行对比评测。","evidence":{"constraints":[]}}',
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
            return httpx.Response(200, json=data)

        user_messages = [
            m.get("content")
            for m in body.get("messages", [])
            if isinstance(m, dict) and m.get("role") == "user"
        ]
        last = user_messages[-1] if user_messages else ""

        # streaming (OpenAI SSE)
        if body.get("stream") is True:
            model = str(body.get("model") or "test-model")
            created = 1730000000
            stream_id = "cmpl-test-stream"
            sse_frames = [
                {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                },
                {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": f"echo: {last}"}, "finish_reason": None}],
                },
                {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                },
            ]
            content = "".join(
                [f"data: {json.dumps(frame, ensure_ascii=False)}\n\n" for frame in sse_frames]
                + ["data: [DONE]\n\n"]
            ).encode("utf-8")
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=content)

        data = {
            "id": "cmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"echo: {last}"},
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(200, json=data)
    return httpx.Response(404, json={"error": "not_found"})


@asynccontextmanager
async def _override_get_http_client():
    transport = httpx.MockTransport(_mock_send)
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        yield client


def _seed_logical_model(redis: InMemoryRedis, logical_id: str) -> None:
    logical = LogicalModel(
        logical_id=logical_id,
        display_name=logical_id,
        description=f"Logical model for {logical_id}",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id="mock",
                model_id=logical_id,
                endpoint="https://mock.local/v1/chat/completions",
                base_weight=1.0,
                region=None,
                max_qps=50,
                meta_hash=None,
                updated_at=1.0,
            )
        ],
        enabled=True,
        updated_at=1.0,
    )
    key = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model=logical.logical_id)
    redis._data[key] = json.dumps(logical.model_dump(), ensure_ascii=False)


@pytest.fixture()
def app_with_mock_chat(monkeypatch):
    monkeypatch.setattr(settings, "mask_as_browser", False, raising=False)
    monkeypatch.setattr(settings, "mask_user_agent", "pytest-client", raising=False)
    monkeypatch.setattr(settings, "mask_origin", None, raising=False)
    monkeypatch.setattr(settings, "mask_referer", None, raising=False)

    cfg = ProviderConfig(
        id="mock",
        name="Mock Provider",
        base_url="https://mock.local",
        api_key="sk-test",  # pragma: allowlist secret
    )

    def _load_provider_configs():
        return [cfg]

    def _get_provider_config(provider_id: str):
        if provider_id == "mock":
            return cfg
        return None

    monkeypatch.setattr("app.provider.config.load_provider_configs", _load_provider_configs)
    monkeypatch.setattr("app.provider.config.get_provider_config", _get_provider_config)
    monkeypatch.setattr("app.routes.load_provider_configs", _load_provider_configs)
    monkeypatch.setattr("app.routes.get_provider_config", _get_provider_config)

    app = create_app()
    SessionLocal = install_inmemory_db(app)

    # Seed a public provider so provider access filtering can succeed.
    from app.models import Provider

    with SessionLocal() as db:
        provider = Provider(provider_id="mock", name="Mock Provider", base_url="https://mock.local")
        db.add(provider)
        db.commit()

    redis = InMemoryRedis()

    async def override_get_redis():
        return redis

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_http_client] = _override_get_http_client

    _seed_logical_model(redis, "test-model")
    _seed_logical_model(redis, "test-model-2")

    yield app, SessionLocal, redis


def _get_seed_ids(SessionLocal):
    from app.models import APIKey, User
    from sqlalchemy import select

    with SessionLocal() as db:
        user = db.execute(select(User)).scalars().first()
        api_key = db.execute(select(APIKey)).scalars().first()
        assert user is not None
        assert api_key is not None
        return user.id, api_key.id


def test_project_eval_config_get_and_update(app_with_mock_chat):
    app, SessionLocal, _ = app_with_mock_chat
    user_id, api_key_id = _get_seed_ids(SessionLocal)
    headers = jwt_auth_headers(str(user_id))

    with TestClient(app) as client:
        resp = client.get(f"/v1/projects/{api_key_id}/eval-config", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == str(api_key_id)
        assert data["enabled"] is True
        assert set(data["provider_scopes"]) == {"private", "shared", "public"}

        resp = client.put(
            f"/v1/projects/{api_key_id}/eval-config",
            headers=headers,
            json={"enabled": False, "candidate_logical_models": ["test-model", "test-model-2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert "candidate_logical_models" in data


def test_assistant_conversation_message_and_eval_flow(app_with_mock_chat, monkeypatch):
    app, SessionLocal, redis = app_with_mock_chat
    user_id, api_key_id = _get_seed_ids(SessionLocal)
    headers = jwt_auth_headers(str(user_id))

    # Patch eval background runner to reuse the same mock transport & redis in tests.
    from app.services import eval_service

    @asynccontextmanager
    async def _http_client_for_eval():
        transport = httpx.MockTransport(_mock_send)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            yield client

    monkeypatch.setattr(eval_service, "_background_http_client", _http_client_for_eval)
    monkeypatch.setattr(eval_service, "_get_background_redis", lambda: redis)
    monkeypatch.setattr(eval_service, "_get_background_session_factory", lambda: SessionLocal)

    with TestClient(app) as client:
        # create assistant
        resp = client.post(
            "/v1/assistants",
            headers=headers,
            json={
                "project_id": str(api_key_id),
                "name": "默认助手",
                "system_prompt": "你是一个严谨的助手",
                "default_logical_model": "test-model",
            },
        )
        assert resp.status_code == 201
        assistant_id = resp.json()["assistant_id"]

        # create conversation
        resp = client.post(
            "/v1/conversations",
            headers=headers,
            json={"assistant_id": assistant_id, "project_id": str(api_key_id), "title": "test"},
        )
        assert resp.status_code == 201
        conversation_id = resp.json()["conversation_id"]

        # message + baseline
        resp = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "你好"},
        )
        assert resp.status_code == 200
        baseline_run_id = resp.json()["baseline_run"]["run_id"]
        message_id = resp.json()["message_id"]

        # enable eval and set candidates
        client.put(
            f"/v1/projects/{api_key_id}/eval-config",
            headers=headers,
            json={"enabled": True, "candidate_logical_models": ["test-model", "test-model-2"]},
        )

        # create eval
        resp = client.post(
            "/v1/evals",
            headers=headers,
            json={
                "project_id": str(api_key_id),
                "assistant_id": assistant_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "baseline_run_id": baseline_run_id,
            },
        )
        assert resp.status_code == 200
        eval_id = resp.json()["eval_id"]
        assert resp.json()["baseline_run_id"] == baseline_run_id
        # In pytest env the challengers are executed inline; eval should become ready unless already rated.
        assert resp.json()["status"] in {"running", "ready"}

        # rating (choose baseline as winner for determinism)
        resp = client.post(
            f"/v1/evals/{eval_id}/rating",
            headers=headers,
            json={"winner_run_id": baseline_run_id, "reason_tags": ["accurate"]},
        )
        assert resp.status_code == 200
        assert resp.json()["winner_run_id"] == baseline_run_id

    from sqlalchemy import select
    from app.models import BanditArmStats

    with SessionLocal() as db:
        rows = db.execute(select(BanditArmStats)).scalars().all()
        assert any(
            isinstance(r.arm_logical_model, str) and "|provider:" in r.arm_logical_model
            for r in rows
        )


def test_eval_context_features_fallback_to_project_ai(app_with_mock_chat, monkeypatch):
    app, SessionLocal, redis = app_with_mock_chat
    user_id, api_key_id = _get_seed_ids(SessionLocal)
    headers = jwt_auth_headers(str(user_id))

    # Patch eval background runner to reuse the same mock transport & redis in tests.
    from app.services import eval_service

    @asynccontextmanager
    async def _http_client_for_eval():
        transport = httpx.MockTransport(_mock_send)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            yield client

    monkeypatch.setattr(eval_service, "_background_http_client", _http_client_for_eval)
    monkeypatch.setattr(eval_service, "_get_background_redis", lambda: redis)
    monkeypatch.setattr(eval_service, "_get_background_session_factory", lambda: SessionLocal)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/assistants",
            headers=headers,
            json={
                "project_id": str(api_key_id),
                "name": "默认助手",
                "system_prompt": "你是一个严谨的助手",
                "default_logical_model": "test-model",
            },
        )
        assert resp.status_code == 201
        assistant_id = resp.json()["assistant_id"]

        resp = client.post(
            "/v1/conversations",
            headers=headers,
            json={"assistant_id": assistant_id, "project_id": str(api_key_id), "title": "test"},
        )
        assert resp.status_code == 201
        conversation_id = resp.json()["conversation_id"]

        # message + baseline: "你好" 会触发 task_type 规则判定为 unknown，从而走 Project AI 兜底。
        resp = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "你好"},
        )
        assert resp.status_code == 200
        baseline_run_id = resp.json()["baseline_run"]["run_id"]
        message_id = resp.json()["message_id"]

        # enable eval + candidates + project ai
        resp = client.put(
            f"/v1/projects/{api_key_id}/eval-config",
            headers=headers,
            json={
                "enabled": True,
                "candidate_logical_models": ["test-model", "test-model-2"],
                "project_ai_enabled": True,
                "project_ai_provider_model": "mock/test-model",
            },
        )
        assert resp.status_code == 200

        resp = client.post(
            "/v1/evals",
            headers=headers,
            json={
                "project_id": str(api_key_id),
                "assistant_id": assistant_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "baseline_run_id": baseline_run_id,
            },
        )
        assert resp.status_code == 200
        eval_id = resp.json()["eval_id"]

    from app.models import Eval
    from sqlalchemy import select

    with SessionLocal() as db:
        row = db.execute(select(Eval).where(Eval.id == UUID(str(eval_id)))).scalars().first()
        assert row is not None
        ctx = row.context_features or {}
        assert isinstance(ctx, dict)
        features = ctx.get("features") or {}
        assert isinstance(features, dict)
        assert features.get("task_type") == "qa"
        assert features.get("risk_tier") == "low"


def test_eval_streaming_sse_parallel(app_with_mock_chat, monkeypatch):
    app, SessionLocal, redis = app_with_mock_chat
    user_id, api_key_id = _get_seed_ids(SessionLocal)
    headers = jwt_auth_headers(str(user_id))

    from app.api.v1 import eval_routes

    @asynccontextmanager
    async def _http_client_for_eval():
        transport = httpx.MockTransport(_mock_send)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            yield client

    monkeypatch.setattr(eval_routes, "_background_http_client", _http_client_for_eval)

    def _read_sse_events(resp: httpx.Response, *, max_events: int = 200):
        events = []
        event_type = None
        data_lines = []
        for line in resp.iter_lines():
            if isinstance(line, (bytes, bytearray)):
                line = line.decode("utf-8", errors="ignore")
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
                continue
            if line.strip() == "":
                if data_lines:
                    data_str = "\n".join(data_lines).strip()
                    events.append((event_type or "message", data_str))
                    if data_str == "[DONE]":
                        break
                    if len(events) >= max_events:
                        break
                event_type = None
                data_lines = []
        return events

    with TestClient(app) as client:
        resp = client.post(
            "/v1/assistants",
            headers=headers,
            json={
                "project_id": str(api_key_id),
                "name": "默认助手",
                "system_prompt": "你是一个严谨的助手",
                "default_logical_model": "test-model",
            },
        )
        assert resp.status_code == 201
        assistant_id = resp.json()["assistant_id"]

        resp = client.post(
            "/v1/conversations",
            headers=headers,
            json={"assistant_id": assistant_id, "project_id": str(api_key_id), "title": "test"},
        )
        assert resp.status_code == 201
        conversation_id = resp.json()["conversation_id"]

        resp = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "你好"},
        )
        assert resp.status_code == 200
        baseline_run_id = resp.json()["baseline_run"]["run_id"]
        message_id = resp.json()["message_id"]

        resp = client.put(
            f"/v1/projects/{api_key_id}/eval-config",
            headers=headers,
            json={"enabled": True, "candidate_logical_models": ["test-model", "test-model-2"]},
        )
        assert resp.status_code == 200

        with client.stream(
            "POST",
            "/v1/evals",
            headers={**headers, "Accept": "text/event-stream"},
            json={
                "project_id": str(api_key_id),
                "assistant_id": assistant_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "baseline_run_id": baseline_run_id,
                "streaming": True,
            },
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            events = _read_sse_events(resp)

        assert any(t == "eval.created" for t, _ in events)
        assert any(t == "run.delta" for t, _ in events)
        assert any(t == "run.completed" for t, _ in events)
        assert any(t == "eval.completed" for t, _ in events)
        assert any(t == "done" and d == "[DONE]" for t, d in events)

    from sqlalchemy import select
    from app.models import Eval, Run

    with SessionLocal() as db:
        eval_row = db.execute(select(Eval).where(Eval.baseline_run_id == UUID(str(baseline_run_id)))).scalars().first()
        assert eval_row is not None
        challenger_ids = [UUID(str(x)) for x in (eval_row.challenger_run_ids or [])]
        assert challenger_ids
        runs = list(db.execute(select(Run).where(Run.id.in_(challenger_ids))).scalars().all())
        assert runs
        assert all(r.status == "succeeded" for r in runs)
        assert all(isinstance(r.output_text, str) and r.output_text for r in runs)
        assert all(isinstance(r.response_payload, dict) for r in runs)


def test_conversation_archive_and_delete(app_with_mock_chat):
    app, SessionLocal, _ = app_with_mock_chat
    user_id, api_key_id = _get_seed_ids(SessionLocal)
    headers = jwt_auth_headers(str(user_id))

    with TestClient(app) as client:
        resp = client.post(
            "/v1/assistants",
            headers=headers,
            json={
                "project_id": str(api_key_id),
                "name": "默认助手",
                "system_prompt": "你是一个严谨的助手",
                "default_logical_model": "test-model",
            },
        )
        assert resp.status_code == 201
        assistant_id = resp.json()["assistant_id"]

        resp = client.post(
            "/v1/conversations",
            headers=headers,
            json={"assistant_id": assistant_id, "project_id": str(api_key_id), "title": "test"},
        )
        assert resp.status_code == 201
        conversation_id = resp.json()["conversation_id"]

        # archive
        resp = client.put(
            f"/v1/conversations/{conversation_id}",
            headers=headers,
            json={"archived": True},
        )
        assert resp.status_code == 200

        # archived conversation should be hidden from list
        resp = client.get(f"/v1/conversations?assistant_id={assistant_id}", headers=headers)
        assert resp.status_code == 200
        ids = [it["conversation_id"] for it in resp.json()["items"]]
        assert str(conversation_id) not in ids

        # but messages can still be read (empty list)
        resp = client.get(f"/v1/conversations/{conversation_id}/messages", headers=headers)
        assert resp.status_code == 200

        # sending new message should fail (get_conversation filters archived)
        resp = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "hello"},
        )
        assert resp.status_code == 404

        # delete
        resp = client.delete(f"/v1/conversations/{conversation_id}", headers=headers)
        assert resp.status_code == 204

        resp = client.get(f"/v1/conversations/{conversation_id}/messages", headers=headers)
        assert resp.status_code == 404
