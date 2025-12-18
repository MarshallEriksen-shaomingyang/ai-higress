from __future__ import annotations

import asyncio
import json
import time

from fastapi.testclient import TestClient

from app.deps import get_redis
from app.models import Provider, ProviderModel
from app.routes import create_app
from app.schemas import LogicalModel, ModelCapability, PhysicalModel
from tests.utils import InMemoryRedis, auth_headers, install_inmemory_db


def test_chat_rejects_when_all_candidates_disabled(monkeypatch) -> None:
    """
    当 provider+model 被禁用后：
    - 路由选择应跳过该候选；
    - 若当前可用 provider 范围内已无任何候选，则返回 400 且提示“该模型已被禁用”。
    """
    app = create_app()
    session_factory = install_inmemory_db(app)

    fake_redis = InMemoryRedis()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis

    with session_factory() as session:
        provider = Provider(
            provider_id="disabled-provider",
            name="Disabled Provider",
            base_url="https://api.example.com",
            transport="http",
            visibility="public",
            weight=1.0,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="gpt-disabled",
                family="gpt",
                display_name="GPT Disabled",
                context_length=8192,
                capabilities=["chat"],
                disabled=True,
            )
        )
        session.commit()

    logical_id = "gpt-disabled"
    logical = LogicalModel(
        logical_id=logical_id,
        display_name=logical_id,
        description="test",
        capabilities=[ModelCapability.CHAT],
        upstreams=[
            PhysicalModel(
                provider_id="disabled-provider",
                model_id="gpt-disabled",
                endpoint="https://api.example.com/v1/chat/completions",
                base_weight=1.0,
                updated_at=time.time(),
                api_style="openai",
            )
        ],
        enabled=True,
        updated_at=time.time(),
    )
    asyncio.run(fake_redis.set(f"llm:logical:{logical_id}", json.dumps(logical.model_dump())))

    monkeypatch.setattr("app.api.v1.chat_routes.ensure_account_usable", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.api.v1.chat_routes.get_accessible_provider_ids",
        lambda *_a, **_k: {"disabled-provider"},
    )

    with TestClient(app, base_url="http://test") as client:
        resp = client.post(
            "/v1/chat/completions",
            headers=auth_headers(),
            json={"model": logical_id, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["detail"]["message"] == "该模型已被禁用"

