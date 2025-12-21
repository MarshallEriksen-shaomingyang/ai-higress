from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Provider, ProviderAPIKey
from app.services.encryption import encrypt_secret
from app.services.provider_audit_service import trigger_provider_test
from app.services.user_probe_executor import ProbeExecutionResult
from app.settings import settings
from tests.utils import InMemoryRedis, jwt_auth_headers, seed_user_and_key


def _create_admin(session):
    admin, _ = seed_user_and_key(
        session,
        token_plain="audit-admin-token",
        username="audit-admin",
        email="audit-admin@example.com",
        is_superuser=True,
    )
    return admin


def _create_public_provider(session, provider_id: str = "audit-provider") -> Provider:
    provider = Provider(
        provider_id=provider_id,
        name="Audit Provider",
        base_url="https://api.audit.example.com",
        provider_type="native",
        transport="http",
        visibility="public",
    )
    session.add(provider)
    session.flush()

    api_key = ProviderAPIKey(
        provider_uuid=provider.id,
        encrypted_key=encrypt_secret("sk-audit-test"),
        weight=1.0,
        max_qps=5,
        label="primary",
        status="active",
    )
    session.add(api_key)
    session.commit()
    session.refresh(provider)
    return provider


def test_admin_trigger_test_updates_status_and_record(monkeypatch, client, db_session):
    admin = _create_admin(db_session)
    provider = _create_public_provider(db_session, "audit-provider-test")
    provider.probe_model = "gpt-4o-mini"
    db_session.add(provider)
    db_session.commit()

    # 使用内存 Redis 和模拟的探针执行，避免网络依赖
    monkeypatch.setattr(
        "app.services.provider_audit_service.get_redis_client",
        lambda: InMemoryRedis(),
    )

    async def _fake_execute_user_probe(*args, **kwargs):
        return ProbeExecutionResult(
            success=True,
            api_style="openai",
            status_code=200,
            latency_ms=42,
            error_message=None,
            response_text="ok",
            response_excerpt="ok",
            response_json={"ok": True},
        )

    monkeypatch.setattr(
        "app.services.provider_audit_service.execute_user_probe",
        _fake_execute_user_probe,
    )

    headers = jwt_auth_headers(str(admin.id))
    resp = client.post(
        f"/admin/providers/{provider.provider_id}/test",
        headers=headers,
        json={"mode": "auto", "remark": "ping"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == provider.provider_id
    assert data["success"] is True
    assert data["mode"] == "auto"
    assert data["probe_results"]
    assert data["probe_results"][0]["input"] == settings.probe_prompt

    db_session.refresh(provider)
    assert provider.audit_status == "testing"
    test_records = db_session.execute(
        select(Provider).where(Provider.id == provider.id)
    ).scalars().first().test_records
    assert test_records  # 确保写入一条测试记录


def test_trigger_provider_test_reuses_db_session(monkeypatch, db_session):
    provider = _create_public_provider(db_session, "audit-provider-session-reuse")

    captured: dict[str, Session | None] = {}

    def _fake_get_provider_config(provider_id: str, session=None):
        captured["session"] = session
        return None

    monkeypatch.setattr(
        "app.services.provider_audit_service.get_provider_config",
        _fake_get_provider_config,
    )

    record = trigger_provider_test(db_session, provider.provider_id, operator_id=None)

    assert captured["session"] is db_session
    assert record.error_code == "config_missing"


def test_admin_update_probe_config(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_public_provider(db_session, "audit-provider-probe-config")
    headers = jwt_auth_headers(str(admin.id))

    resp = client.put(
        f"/admin/providers/{provider.provider_id}/probe-config",
        headers=headers,
        json={
            "probe_enabled": False,
            "probe_interval_seconds": 900,
            "probe_model": "gpt-4o-mini",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["probe_enabled"] is False
    assert data["probe_interval_seconds"] == 900
    assert data["probe_model"] == "gpt-4o-mini"

    db_session.refresh(provider)
    assert provider.probe_enabled is False
    assert provider.probe_interval_seconds == 900
    assert provider.probe_model == "gpt-4o-mini"


def test_admin_approve_limited_sets_audit_and_limit(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_public_provider(db_session, "audit-provider-approve")
    headers = jwt_auth_headers(str(admin.id))

    resp = client.post(
        f"/admin/providers/{provider.provider_id}/approve-limited",
        headers=headers,
        json={"remark": "limit to qps 2", "limit_qps": 2},
    )
    assert resp.status_code == 200

    db_session.refresh(provider)
    assert provider.audit_status == "approved_limited"
    assert provider.operation_status == "active"
    assert provider.max_qps == 2


def test_admin_pause_and_resume_provider(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_public_provider(db_session, "audit-provider-pause")
    headers = jwt_auth_headers(str(admin.id))

    resp_pause = client.post(
        f"/admin/providers/{provider.provider_id}/pause",
        headers=headers,
        json={"remark": "maintenance"},
    )
    assert resp_pause.status_code == 200
    db_session.refresh(provider)
    assert provider.operation_status == "paused"

    resp_resume = client.post(
        f"/admin/providers/{provider.provider_id}/resume",
        headers=headers,
        json={"remark": "done"},
    )
    assert resp_resume.status_code == 200
    db_session.refresh(provider)
    assert provider.operation_status == "active"


def test_reject_requires_remark(client, db_session):
    admin = _create_admin(db_session)
    provider = _create_public_provider(db_session, "audit-provider-reject")
    headers = jwt_auth_headers(str(admin.id))

    resp = client.post(
        f"/admin/providers/{provider.provider_id}/reject",
        headers=headers,
        json={},
    )
    assert resp.status_code == 400

    resp_ok = client.post(
        f"/admin/providers/{provider.provider_id}/reject",
        headers=headers,
        json={"remark": "bad upstream"},
    )
    assert resp_ok.status_code == 200
    db_session.refresh(provider)
    assert provider.audit_status == "rejected"
