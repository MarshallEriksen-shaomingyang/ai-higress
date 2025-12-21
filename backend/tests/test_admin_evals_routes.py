from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import (
    AssistantPreset,
    Conversation,
    Eval,
    EvalRating,
    Message,
    Run,
    User,
)
from app.routes import create_app
from tests.utils import install_inmemory_db, jwt_auth_headers, seed_user_and_key


def _headers(user_id: str) -> dict[str, str]:
    return jwt_auth_headers(user_id)


def _seed_eval(
    *,
    db,
    user_id: UUID,
    api_key_id: UUID,
    baseline_model: str = "baseline-model",
    challenger_model: str = "challenger-model",
    status: str = "ready",
    with_rating: bool = False,
) -> Eval:
    now = datetime.now(UTC)

    assistant = AssistantPreset(
        user_id=user_id,
        api_key_id=api_key_id,
        name=f"assistant-{baseline_model}",
        system_prompt="",
        default_logical_model=baseline_model,
        title_logical_model=None,
        model_preset=None,
        archived_at=None,
    )
    db.add(assistant)
    db.flush()

    conv = Conversation(
        user_id=user_id,
        api_key_id=api_key_id,
        assistant_id=assistant.id,
        title="",
        last_activity_at=now,
        archived_at=None,
        is_pinned=False,
        last_message_content=None,
        unread_count=0,
    )
    db.add(conv)
    db.flush()

    msg = Message(
        conversation_id=conv.id,
        role="user",
        content={"type": "text", "text": "secret-user-text"},
        sequence=1,
    )
    db.add(msg)
    db.flush()

    baseline_run = Run(
        eval_id=None,
        message_id=msg.id,
        user_id=user_id,
        api_key_id=api_key_id,
        requested_logical_model=baseline_model,
        selected_provider_id="p1",
        selected_provider_model="m1",
        status="succeeded",
        started_at=now,
        finished_at=now,
        latency_ms=123,
        cost_credits=2,
        error_code=None,
        error_message=None,
        request_payload=None,
        response_payload=None,
        output_text="SECRET_OUTPUT_TEXT",
        output_preview="SECRET_PREVIEW",
    )
    db.add(baseline_run)
    db.flush()

    challenger_run = Run(
        eval_id=None,
        message_id=msg.id,
        user_id=user_id,
        api_key_id=api_key_id,
        requested_logical_model=challenger_model,
        selected_provider_id="p2",
        selected_provider_model="m2",
        status="failed",
        started_at=now,
        finished_at=now,
        latency_ms=456,
        cost_credits=3,
        error_code="UPSTREAM_ERROR",
        error_message="",
        request_payload=None,
        response_payload=None,
        output_text="SECRET_CHALLENGER_TEXT",
        output_preview="SECRET_CHALLENGER_PREVIEW",
    )
    db.add(challenger_run)
    db.flush()

    eval_row = Eval(
        user_id=user_id,
        api_key_id=api_key_id,
        assistant_id=assistant.id,
        conversation_id=conv.id,
        message_id=msg.id,
        baseline_run_id=baseline_run.id,
        challenger_run_ids=[str(challenger_run.id)],
        effective_provider_ids=["p1", "p2"],
        context_features=None,
        policy_version="ts-v1",
        explanation={"summary": "ok", "evidence": {"exploration": True}},
        status=status,
        rated_at=None,
    )
    db.add(eval_row)
    db.flush()

    if with_rating:
        rating = EvalRating(
            eval_id=eval_row.id,
            user_id=user_id,
            winner_run_id=baseline_run.id,
            reason_tags=["fast"],
        )
        db.add(rating)
        eval_row.status = "rated"
        eval_row.rated_at = now
        db.add(eval_row)

    db.commit()
    db.refresh(eval_row)
    return eval_row


def test_admin_evals_requires_superuser():
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user, _ = seed_user_and_key(
            session,
            token_plain="user-token-evals",
            username="normal-user-evals",
            email="normal-evals@example.com",
            is_superuser=False,
        )
        user_id = str(user.id)

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.get("/admin/evals", headers=_headers(user_id))

    assert resp.status_code == 403


def test_admin_can_list_evals_without_chat_content_or_output_preview():
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        admin = session.execute(select(User).where(User.is_superuser.is_(True))).scalars().first()
        assert admin is not None
        admin_id = str(admin.id)

        # 直接从 api_keys 表查出 admin 的首个 key（seed_user_and_key 会创建一条）。
        from app.models import APIKey

        admin_api_key = session.execute(select(APIKey).where(APIKey.user_id == admin.id)).scalars().first()
        assert admin_api_key is not None

        other_user, other_key = seed_user_and_key(
            session,
            token_plain="other-token-evals",
            username="other-user-evals",
            email="other-evals@example.com",
            is_superuser=False,
        )

        eval_a = _seed_eval(
            db=session,
            user_id=UUID(str(admin.id)),
            api_key_id=UUID(str(admin_api_key.id)),
            baseline_model="baseline-a",
            challenger_model="challenger-a",
            status="ready",
            with_rating=True,
        )
        eval_b = _seed_eval(
            db=session,
            user_id=UUID(str(other_user.id)),
            api_key_id=UUID(str(other_key.id)),
            baseline_model="baseline-b",
            challenger_model="challenger-b",
            status="running",
            with_rating=False,
        )

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.get("/admin/evals", headers=_headers(admin_id), params={"limit": 50})
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data.get("items"), list)
        eval_ids = {item["eval_id"] for item in data["items"]}
        assert str(eval_a.id) in eval_ids
        assert str(eval_b.id) in eval_ids

        # 不应返回任何 run output 字段（output_text/output_preview）
        for item in data["items"]:
            baseline_run = item.get("baseline_run") or {}
            assert "output_text" not in baseline_run
            assert "output_preview" not in baseline_run
            for ch in item.get("challengers") or []:
                assert "output_text" not in ch
                assert "output_preview" not in ch

        # rated 的评测应包含 rating（不含内容，仅 winner+tags）
        rated_item = next((it for it in data["items"] if it["eval_id"] == str(eval_a.id)), None)
        assert rated_item is not None
        assert rated_item["status"] == "rated"
        assert rated_item.get("rating") is not None
        assert rated_item["rating"]["reason_tags"] == ["fast"]


def test_admin_evals_support_status_filter():
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        admin = session.execute(select(User).where(User.is_superuser.is_(True))).scalars().first()
        assert admin is not None
        admin_id = str(admin.id)

        from app.models import APIKey

        admin_api_key = session.execute(select(APIKey).where(APIKey.user_id == admin.id)).scalars().first()
        assert admin_api_key is not None

        _seed_eval(
            db=session,
            user_id=UUID(str(admin.id)),
            api_key_id=UUID(str(admin_api_key.id)),
            baseline_model="baseline-ready",
            challenger_model="challenger-ready",
            status="ready",
        )
        _seed_eval(
            db=session,
            user_id=UUID(str(admin.id)),
            api_key_id=UUID(str(admin_api_key.id)),
            baseline_model="baseline-running",
            challenger_model="challenger-running",
            status="running",
        )

    with TestClient(app, base_url="http://testserver") as client:
        resp = client.get("/admin/evals", headers=_headers(admin_id), params={"status": "running"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["status"] == "running" for item in data.get("items", []))
