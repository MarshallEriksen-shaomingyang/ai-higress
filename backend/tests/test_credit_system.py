from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# 确保项目根目录在 sys.path 中，便于直接 import app.*
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.routes import create_app  # noqa: E402
from app.settings import settings  # noqa: E402
from app.models import (  # noqa: E402
    CreditAccount,
    CreditTransaction,
    ModelBillingConfig,
    Provider,
    ProviderModel,
    User,
)
from app.services.credit_service import (  # noqa: E402
    InsufficientCreditsError,
    ensure_account_usable,
    get_or_create_account_for_user,
    record_chat_completion_usage,
)
from tests.utils import (  # noqa: E402
    install_inmemory_db,
    jwt_auth_headers,
)


def _get_single_user(session: Session) -> User:
    return session.query(User).first()


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

        payload = {"usage": {"total_tokens": 1000}}

        # baseline：billing_factor=1.0
        before = account.balance
        record_chat_completion_usage(
            session,
            user_id=user_id,
            api_key_id=None,
            model_name="test-model",
            provider_id="p1",
            payload=payload,
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
            model_name="test-model",
            provider_id="p1",
            payload=payload,
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
            model_name="pricing-model",
            provider_id="p-pricing",
            payload=payload,
            is_stream=False,
        )
        session.refresh(account)
        cost = before - account.balance

        # 预期扣费：
        # - 输入：1k tokens × 5 credits/1k = 5
        # - 输出：1k tokens × 10 credits/1k = 10
        # - 总计：15 credits（multiplier=1.0，billing_factor 默认为 1.0）
        assert cost == 15
