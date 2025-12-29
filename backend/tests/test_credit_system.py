from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# 确保项目根目录在 sys.path 中，便于直接 import app.*
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from datetime import UTC

from app.models import (  # noqa: E402
    CreditAccount,
    CreditTransaction,
    ModelBillingConfig,
    Provider,
    ProviderModel,
    User,
)
from app.routes import create_app  # noqa: E402
from app.services.credit_service import (  # noqa: E402
    InsufficientCreditsError,
    ensure_account_usable,
    get_auto_topup_rule_for_user,
    get_or_create_account_for_user,
    record_chat_completion_usage,
    run_daily_auto_topups,
)
from app.settings import settings  # noqa: E402
from tests.utils import (  # noqa: E402
    install_inmemory_db,
    jwt_auth_headers,
    seed_user_and_key,
)


def _get_single_user(session: Session) -> User:
    return session.query(User).first()


def _create_priced_provider_model(
    session: Session,
    *,
    provider: Provider,
    model_id: str,
    pricing: dict[str, float],
) -> ProviderModel:
    model = ProviderModel(
        provider_id=provider.id,
        model_id=model_id,
        family="test-family",
        display_name=f"{model_id}-display",
        context_length=8192,
        capabilities=["chat"],
        pricing=pricing,
    )
    session.add(model)
    session.commit()
    return model


def test_credit_endpoints_basic_flow(monkeypatch):
    """
    验证积分相关 REST 接口的基本链路：
    - /v1/credits/me 自动初始化账户；
    - 管理员通过 /v1/credits/admin/users/{id}/topup 充值；
    - /v1/credits/me/transactions 能看到对应流水。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    # 取出种子用户（默认是超级管理员）
    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

    headers = jwt_auth_headers(str(user_id))

    with TestClient(app=app, base_url="http://testserver") as client:
        # 1) 首次访问 /v1/credits/me，应创建一个初始余额为 0 的账户
        resp = client.get("/v1/credits/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(user_id)
        assert data["balance"] == settings.initial_user_credits

        # 2) 管理员给自己充值 100 积分
        resp = client.post(
            f"/v1/credits/admin/users/{user_id}/topup",
            headers=headers,
            json={"amount": 100, "description": "test topup"},
        )
        assert resp.status_code == 200
        account_after = resp.json()
        assert account_after["balance"] == settings.initial_user_credits + 100

        # 3) 查询流水，应该至少包含一条充值记录
        resp = client.get("/v1/credits/me/transactions", headers=headers)
        assert resp.status_code == 200
        transactions = resp.json()
        assert isinstance(transactions, list)
        assert transactions, "充值后应该至少有一条积分流水"
        first = transactions[0]
        assert first["amount"] == 100
        assert first["reason"] == "admin_topup"


def test_credit_admin_grant_is_idempotent():
    """
    验证管理员“积分入账”接口的幂等行为：
    - 首次调用 applied=true 且余额增加；
    - 使用相同 idempotency_key 重复调用 applied=false 且余额不再增加；
    - 幂等重复时仍返回已存在的流水信息。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

    headers = jwt_auth_headers(str(user_id))
    idem_key = f"test:grant:{user_id}:once"

    with TestClient(app=app, base_url="http://testserver") as client:
        resp = client.get("/v1/credits/me", headers=headers)
        assert resp.status_code == 200
        initial_balance = resp.json()["balance"]

        payload = {
            "amount": 50,
            "reason": "sign_in",
            "description": "daily sign in reward",
            "idempotency_key": idem_key,
        }

        resp = client.post(
            f"/v1/credits/admin/users/{user_id}/grant",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] is True
        assert data["account"]["balance"] == initial_balance + 50
        assert data["transaction"] is not None
        assert data["transaction"]["amount"] == 50
        assert data["transaction"]["reason"] == "sign_in"

        resp = client.post(
            f"/v1/credits/admin/users/{user_id}/grant",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        data2 = resp.json()
        assert data2["applied"] is False
        assert data2["account"]["balance"] == initial_balance + 50
        assert data2["transaction"] is not None
        assert data2["transaction"]["amount"] == 50
        assert data2["transaction"]["reason"] == "sign_in"

        resp = client.get("/v1/credits/me/transactions", headers=headers)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 1
        assert txs[0]["amount"] == 50
        assert txs[0]["reason"] == "sign_in"


def test_credit_grant_token_issue_and_redeem_is_idempotent():
    """
    验证“积分入账 token”签发与兑换：
    - 管理员签发 token；
    - 首次兑换 applied=true；
    - 重复兑换 applied=false；
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        admin = _get_single_user(session)
        admin_id = admin.id

    headers_admin = jwt_auth_headers(str(admin_id))

    with TestClient(app=app, base_url="http://testserver") as client:
        resp = client.get("/v1/credits/me", headers=headers_admin)
        assert resp.status_code == 200
        initial_balance = resp.json()["balance"]

        issue_payload = {
            "user_id": str(admin_id),
            "amount": 30,
            "reason": "redeem_code",
            "description": "test redeem",
            "idempotency_key": f"test:redeem:{admin_id}:once",
            "expires_in_seconds": 3600,
        }
        resp = client.post(
            "/v1/credits/admin/grant-tokens",
            headers=headers_admin,
            json=issue_payload,
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        assert token

        resp = client.post(
            "/v1/credits/me/grant-token",
            headers=headers_admin,
            json={"token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] is True
        assert data["account"]["balance"] == initial_balance + 30
        assert data["transaction"] is not None
        assert data["transaction"]["amount"] == 30
        assert data["transaction"]["reason"] == "redeem_code"

        resp = client.post(
            "/v1/credits/me/grant-token",
            headers=headers_admin,
            json={"token": token},
        )
        assert resp.status_code == 200
        data2 = resp.json()
        assert data2["applied"] is False
        assert data2["account"]["balance"] == initial_balance + 30


def test_credit_grant_token_can_be_user_bound_and_global_one_time():
    """
    验证 token 的两种典型模式：
    - user-bound：仅允许指定用户兑换；
    - global one-time：不绑定用户，但通过全局唯一 idempotency_key 限制仅首个兑换者成功。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        admin = _get_single_user(session)
        admin_id = admin.id
        user2, _ = seed_user_and_key(
            session,
            token_plain="timeline-2",
            username="user2",
            email="user2@example.com",
            is_superuser=False,
        )
        user2_id = user2.id

    headers_admin = jwt_auth_headers(str(admin_id))
    headers_user2 = jwt_auth_headers(str(user2_id))

    with TestClient(app=app, base_url="http://testserver") as client:
        # 1) user-bound token 仅允许 user2 兑换
        resp = client.post(
            "/v1/credits/admin/grant-tokens",
            headers=headers_admin,
            json={
                "user_id": str(user2_id),
                "amount": 10,
                "reason": "promo",
                "description": "user-bound promo",
                "idempotency_key": f"test:promo:user2:{user2_id}",
                "expires_in_seconds": 3600,
            },
        )
        assert resp.status_code == 200
        token_user2 = resp.json()["token"]

        resp = client.post(
            "/v1/credits/me/grant-token",
            headers=headers_admin,
            json={"token": token_user2},
        )
        assert resp.status_code == 403

        resp = client.post(
            "/v1/credits/me/grant-token",
            headers=headers_user2,
            json={"token": token_user2},
        )
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

        # 2) global one-time：第一个兑换者成功，第二个兑换者应冲突
        resp = client.post(
            "/v1/credits/admin/grant-tokens",
            headers=headers_admin,
            json={
                "user_id": None,
                "amount": 5,
                "reason": "redeem_code",
                "description": "global one-time",
                "idempotency_key": "test:global:redeem:once",
                "expires_in_seconds": 3600,
            },
        )
        assert resp.status_code == 200
        token_global = resp.json()["token"]

        resp = client.post(
            "/v1/credits/me/grant-token",
            headers=headers_user2,
            json={"token": token_global},
        )
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

        resp = client.post(
            "/v1/credits/me/grant-token",
            headers=headers_admin,
            json={"token": token_global},
        )
        assert resp.status_code == 409


def test_ensure_account_usable_respects_enable_credit_check(monkeypatch):
    """
    确认 ensure_account_usable 在启用积分校验时会阻止余额不足的用户调用，
    在未启用时则不抛出异常。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

        # 显式创建一个余额为 0 的积分账户
        account = get_or_create_account_for_user(session, user_id)
        account.balance = 0
        session.commit()

        # 1) 未开启 ENABLE_CREDIT_CHECK 时，应该直接放行
        monkeypatch.setattr(settings, "enable_credit_check", False, raising=False)
        ensure_account_usable(session, user_id=user_id)

        # 2) 开启 ENABLE_CREDIT_CHECK 且余额为 0 时，应抛出 InsufficientCreditsError
        monkeypatch.setattr(settings, "enable_credit_check", True, raising=False)
        try:
            ensure_account_usable(session, user_id=user_id)
            assert False, "expected InsufficientCreditsError"
        except InsufficientCreditsError as exc:
            assert exc.balance == 0

        # 3) 手动把余额调为正数后，再次调用应不再抛错
        account.balance = 50
        session.commit()
        ensure_account_usable(session, user_id=user_id)


def test_provider_billing_factor_affects_cost(monkeypatch):
    """
    同一模型在不同 Provider 下，billing_factor 不同应导致扣费不同。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

        # 创建一个 Provider 和模型计费配置
        provider = Provider(
            provider_id="p1",
            name="Provider 1",
            base_url="https://p1.local",
            transport="http",
        )
        session.add(provider)

        mb = ModelBillingConfig(
            model_name="test-model",
            multiplier=1.0,
            is_active=True,
        )
        session.add(mb)
        session.commit()

        # 初始化积分账户，设置足够大的余额防止负数
        account = get_or_create_account_for_user(session, user_id)
        account.balance = 10_000
        session.commit()

        _create_priced_provider_model(
            session,
            provider=provider,
            model_id="test-model",
            pricing={"input": 1.0, "output": 1.0},
        )

        payload = {"usage": {"prompt_tokens": 1000, "completion_tokens": 1000}}

        # baseline：billing_factor=1.0
        before = account.balance
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="test-model",
            provider_id="p1",
            provider_model_id="test-model",
            response_payload=payload,
            is_stream=False,
        )
        session.refresh(account)
        cost_base = before - account.balance

        # 将 Provider 的结算系数改为 2.0，再调用一次
        account.balance = 10_000
        provider.billing_factor = 2.0
        session.commit()

        before2 = account.balance
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="test-model",
            provider_id="p1",
            provider_model_id="test-model",
            response_payload=payload,
            is_stream=False,
        )
        session.refresh(account)
        cost_high = before2 - account.balance

        assert cost_base > 0
        assert cost_high == cost_base * 2


def test_provider_model_pricing_overrides_legacy_pricing(monkeypatch):
    """
    当 provider_models.pricing 配置了每模型定价时，应优先按该价格计费。

    约定：
    - pricing.input / pricing.output 为每 1000 tokens 的积分单价；
    - 仍会叠加 ModelBillingConfig.multiplier 与 Provider.billing_factor。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

        # 创建 Provider 与其下的模型行，并配置 per-model pricing。
        provider = Provider(
            provider_id="p-pricing",
            name="Provider Pricing",
            base_url="https://p-pricing.local",
            transport="http",
        )
        session.add(provider)
        session.flush()  # 确保 provider.id 可用

        # 模型计费倍率为 1.0，方便断言。
        mb = ModelBillingConfig(
            model_name="pricing-model",
            multiplier=1.0,
            is_active=True,
        )
        session.add(mb)

        model = ProviderModel(
            provider_id=provider.id,
            model_id="pricing-model",
            family="pricing-family",
            display_name="Pricing Model",
            context_length=8192,
            capabilities=["chat"],
            pricing={"input": 5.0, "output": 10.0},
        )
        session.add(model)
        session.commit()

        account = get_or_create_account_for_user(session, user_id)
        account.balance = 10_000
        session.commit()

        payload = {
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 1000,
                "total_tokens": 2000,
            }
        }

        before = account.balance
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="pricing-model",
            provider_id="p-pricing",
            provider_model_id="pricing-model",
            response_payload=payload,
            is_stream=False,
        )
        session.refresh(account)
        cost = before - account.balance

        # 预期扣费：
        # - 输入：1k tokens × 5 credits/1k = 5
        # - 输出：1k tokens × 10 credits/1k = 10
        # - 总计：15 credits（multiplier=1.0，billing_factor 默认为 1.0）
        assert cost == 15


def test_credit_consumption_api_and_provider_breakdown(monkeypatch):
    """
    新增的积分消耗分析接口应返回汇总、Provider 排行以及时间序列数据。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)
    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id
        headers = jwt_auth_headers(str(user_id))

        provider_a = Provider(
            provider_id="provider-a",
            name="Provider A",
            base_url="https://a.local",
            transport="http",
        )
        provider_b = Provider(
            provider_id="provider-b",
            name="Provider B",
            base_url="https://b.local",
            transport="http",
        )
        session.add_all([provider_a, provider_b])
        session.commit()

        _create_priced_provider_model(
            session,
            provider=provider_a,
            model_id="model-a",
            pricing={"input": 1.0, "output": 1.0},
        )
        _create_priced_provider_model(
            session,
            provider=provider_b,
            model_id="model-b",
            pricing={"input": 1.0, "output": 1.0},
        )

        account = get_or_create_account_for_user(session, user_id)
        account.balance = 1_000
        session.commit()

        payload = {"usage": {"total_tokens": 1000}}
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="logic-a",
            provider_id="provider-a",
            provider_model_id="model-a",
            response_payload=payload,
        )
        payload_large = {"usage": {"total_tokens": 2000}}
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="logic-a",
            provider_id="provider-a",
            provider_model_id="model-a",
            response_payload=payload_large,
        )
        payload_small = {"usage": {"total_tokens": 500}}
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="logic-b",
            provider_id="provider-b",
            provider_model_id="model-b",
            response_payload=payload_small,
        )

        session.commit()

    with TestClient(app=app, base_url="http://testserver") as client:
        summary_resp = client.get(
            "/v1/credits/me/consumption/summary",
            params={"time_range": "7d"},
            headers=headers,
        )
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["spent_credits"] == 4
        assert summary["transactions"] == 3
        assert summary["avg_daily_spent"] > 0
        assert summary["projected_days_left"] is not None

        provider_resp = client.get(
            "/v1/credits/me/consumption/providers",
            params={"time_range": "7d"},
            headers=headers,
        )
        assert provider_resp.status_code == 200
        provider_data = provider_resp.json()
        assert provider_data["total_spent"] == 4
        assert len(provider_data["items"]) == 2
        assert provider_data["items"][0]["provider_id"] == "provider-a"
        assert provider_data["items"][0]["total_spent"] == 3
        assert provider_data["items"][1]["provider_id"] == "provider-b"
        assert provider_data["items"][1]["total_spent"] == 1

        series_resp = client.get(
            "/v1/credits/me/consumption/timeseries",
            params={"time_range": "7d"},
            headers=headers,
        )
        assert series_resp.status_code == 200
        series = series_resp.json()
        assert series["bucket"] == "day"
        assert series["points"], "应至少返回 1 个时间点"
        total_points_spent = sum(point["spent_credits"] for point in series["points"])
        assert total_points_spent == 4


def test_record_usage_skips_without_provider_pricing():
    """
    未在 ProviderModel.pricing 中设置单价时，应跳过积分扣费，仅记录 usage。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

        provider = Provider(
            provider_id="provider-no-price",
            name="Provider No Price",
            base_url="https://noprice.local",
            transport="http",
        )
        session.add(provider)
        session.commit()

        account = get_or_create_account_for_user(session, user_id)
        account.balance = 500
        session.commit()

        payload = {"usage": {"total_tokens": 1000}}
        before = account.balance
        cost = record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            logical_model_name="logic-np",
            provider_id="provider-no-price",
            provider_model_id="missing-model",
            response_payload=payload,
        )
        session.refresh(account)

        assert cost == 0
        assert account.balance == before


def test_auto_topup_rule_and_daily_task(monkeypatch):
    """
    验证自动充值规则与定时任务执行逻辑：
    - 管理员通过 /v1/credits/admin/users/{id}/auto-topup 配置规则；
    - 当余额低于阈值时，run_daily_auto_topups 会自动补足余额；
    - 关闭规则或余额高于阈值时不会重复充值。
    """
    app = create_app()
    SessionLocal = install_inmemory_db(app)

    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

    headers = jwt_auth_headers(str(user_id))

    with TestClient(app=app, base_url="http://testserver") as client:
        # 1) 确保账户存在，并设置一个较低的初始余额
        with SessionLocal() as session:
            account = get_or_create_account_for_user(session, user_id)
            account.balance = 50
            session.commit()

        # 2) 管理员为该用户配置自动充值规则：
        #    当余额 < 100 时自动补到 200
        resp = client.put(
            f"/v1/credits/admin/users/{user_id}/auto-topup",
            headers=headers,
            json={
                "min_balance_threshold": 100,
                "target_balance": 200,
                "is_active": True,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == str(user_id)
        assert data["min_balance_threshold"] == 100
        assert data["target_balance"] == 200
        assert data["is_active"] is True

        # 3) 调用服务层的 run_daily_auto_topups，模拟一次定时任务执行
        with SessionLocal() as session:
            processed = run_daily_auto_topups(session)
            assert processed == 1

            account = session.query(CreditAccount).filter_by(user_id=user_id).one()
            assert account.balance == 200

            # 应该能找到一条自动充值流水
            tx = (
                session.query(CreditTransaction)
                .filter_by(user_id=user_id, reason="auto_daily_topup")
                .order_by(CreditTransaction.created_at.desc())
                .first()
            )
            assert tx is not None
            assert tx.amount == 150

            # 再次执行任务，因为余额已达到目标值，不应重复充值
            processed_again = run_daily_auto_topups(session)
            assert processed_again == 0

        # 4) 管理员关闭自动充值规则
        resp = client.delete(
            f"/v1/credits/admin/users/{user_id}/auto-topup",
            headers=headers,
        )
        assert resp.status_code == 204

        # 规则应已被标记为 inactive
        with SessionLocal() as session:
            rule = get_auto_topup_rule_for_user(session, user_id)
            assert rule is not None
            assert rule.is_active is False


def test_transaction_filtering_by_reason_and_date(monkeypatch):
    """
    验证 /v1/credits/me/transactions 端点的过滤功能：
    - 按 reason（原因）过滤
    - 按日期范围过滤
    """
    from datetime import datetime, timedelta

    app = create_app()
    SessionLocal = install_inmemory_db(app)

    # 取出种子用户（默认是超级管理员）
    with SessionLocal() as session:
        user = _get_single_user(session)
        user_id = user.id

    headers = jwt_auth_headers(str(user_id))

    with TestClient(app=app, base_url="http://testserver") as client:
        # 1) 初始化账户
        resp = client.get("/v1/credits/me", headers=headers)
        assert resp.status_code == 200

        # 2) 创建多笔不同 reason 的流水
        # 充值一次
        resp = client.post(
            f"/v1/credits/admin/users/{user_id}/topup",
            headers=headers,
            json={"amount": 100, "description": "test topup 1"},
        )
        assert resp.status_code == 200

        # 再充值一次（产生第二条admin_topup记录）
        resp = client.post(
            f"/v1/credits/admin/users/{user_id}/topup",
            headers=headers,
            json={"amount": 50, "description": "test topup 2"},
        )
        assert resp.status_code == 200

        # 3) 查询所有流水
        resp = client.get("/v1/credits/me/transactions", headers=headers)
        assert resp.status_code == 200
        all_transactions = resp.json()
        assert len(all_transactions) >= 2

        # 4) 按 reason 过滤：只查询 admin_topup
        resp = client.get(
            "/v1/credits/me/transactions",
            headers=headers,
            params={"reason": "admin_topup"},
        )
        assert resp.status_code == 200
        admin_topup_transactions = resp.json()
        assert len(admin_topup_transactions) >= 2
        # 验证都是 admin_topup
        for tx in admin_topup_transactions:
            assert tx["reason"] == "admin_topup"

        # 5) 按 reason 过滤：查询不存在的reason（应返回空列表）
        resp = client.get(
            "/v1/credits/me/transactions",
            headers=headers,
            params={"reason": "nonexistent_reason"},
        )
        assert resp.status_code == 200
        empty_transactions = resp.json()
        assert len(empty_transactions) == 0

        # 6) 按日期范围过滤：获取 ISO 格式的日期
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        future_date = (now + timedelta(days=1)).isoformat()

        resp = client.get(
            "/v1/credits/me/transactions",
            headers=headers,
            params={
                "start_date": today_start.isoformat(),
                "end_date": future_date,
            },
        )
        assert resp.status_code == 200
        today_transactions = resp.json()
        assert len(today_transactions) >= 2

        # 7) 组合过滤：按日期和reason都过滤
        resp = client.get(
            "/v1/credits/me/transactions",
            headers=headers,
            params={
                "reason": "admin_topup",
                "start_date": today_start.isoformat(),
                "end_date": future_date,
            },
        )
        assert resp.status_code == 200
        filtered_transactions = resp.json()
        assert len(filtered_transactions) >= 2
        for tx in filtered_transactions:
            assert tx["reason"] == "admin_topup"

        # 8) 测试无效日期格式
        resp = client.get(
            "/v1/credits/me/transactions",
            headers=headers,
            params={"start_date": "invalid-date"},
        )
        assert resp.status_code == 400
