from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import (
    CreditAccount,
    CreditTransaction,
    ModelBillingConfig,
    Provider,
    ProviderModel,
)
from app.settings import settings


class InsufficientCreditsError(Exception):
    """表示当前用户积分不足或账户不可用，用于在网关层统一转换为 HTTP 错误。"""

    def __init__(self, message: str, *, balance: int, required: int) -> None:
        super().__init__(message)
        self.balance = balance
        self.required = required


def get_or_create_account_for_user(db: Session, user_id: UUID) -> CreditAccount:
    """
    获取用户积分账户；若不存在则按配置初始化一个新的账户。
    """
    account = db.execute(
        select(CreditAccount).where(CreditAccount.user_id == user_id)
    ).scalar_one_or_none()
    if account is not None:
        return account

    initial_balance = max(0, int(getattr(settings, "initial_user_credits", 0)))
    account = CreditAccount(user_id=user_id, balance=initial_balance)
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info(
        "Created credit account for user %s with initial balance=%s",
        user_id,
        initial_balance,
    )
    return account


def ensure_account_usable(db: Session, *, user_id: UUID) -> None:
    """
    在网关入口处调用：检查用户积分账户是否可用。

    - 若未开启 ENABLE_CREDIT_CHECK，则直接放行（只做被动记账，不做拦截）；
    - 若已开启，则要求账户状态为 active 且 balance > 0。
    """
    if not getattr(settings, "enable_credit_check", False):
        return

    account = get_or_create_account_for_user(db, user_id)
    if account.status != "active":
        raise InsufficientCreditsError(
            "积分账户已冻结或不可用",
            balance=int(account.balance),
            required=0,
        )
    if account.balance <= 0:
        raise InsufficientCreditsError(
            "积分不足，请先充值后再调用接口",
            balance=int(account.balance),
            required=1,
        )


def _load_multiplier_for_model(db: Session, model_name: str | None) -> float:
    if not model_name:
        return 1.0
    try:
        cfg = (
            db.execute(
                select(ModelBillingConfig)
                .where(ModelBillingConfig.model_name == model_name)
                .where(ModelBillingConfig.is_active.is_(True))
            )
            .scalars()
            .first()
        )
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception("Failed to load ModelBillingConfig for model %r", model_name)
        return 1.0
    if cfg is None:
        return 1.0
    try:
        return float(cfg.multiplier or 1.0)
    except Exception:
        return 1.0


def _load_provider_model_pricing(
    db: Session,
    *,
    provider_id: str | None,
    model_name: str | None,
) -> tuple[float | None, float | None]:
    """
    按 provider+model 维度读取定价信息。

    约定：
    - pricing 字段存放在 provider_models.pricing JSON 中；
    - 单位为「每 1000 tokens 消耗的积分数」；
    - key 使用 "input" / "output" 分别表示输入 / 输出 token 单价。
    """
    if not provider_id or not model_name:
        return None, None

    try:
        pricing_json = (
            db.execute(
                select(ProviderModel.pricing)
                .join(Provider, ProviderModel.provider_id == Provider.id)
                .where(Provider.provider_id == provider_id)
                .where(ProviderModel.model_id == model_name)
            )
            .scalars()
            .first()
        )
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to load ProviderModel.pricing for provider=%r model=%r",
            provider_id,
            model_name,
        )
        return None, None

    if not isinstance(pricing_json, dict):
        return None, None

    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    return _to_float(pricing_json.get("input")), _to_float(
        pricing_json.get("output")
    )


def _load_provider_factor(db: Session, provider_id: str | None) -> float:
    """
    根据 provider_id 读取结算系数。

    - provider_id 为空时返回 1.0；
    - 查询不到或字段异常时也回退到 1.0。
    """
    if not provider_id:
        return 1.0
    try:
        provider = (
            db.execute(
                select(Provider).where(Provider.provider_id == provider_id)
            )
            .scalars()
            .first()
        )
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception("Failed to load Provider for provider_id=%r", provider_id)
        return 1.0
    if provider is None:
        return 1.0
    try:
        return float(provider.billing_factor or 1.0)
    except Exception:
        return 1.0


def _compute_cost_credits(
    *,
    db: Session,
    model_name: str | None,
    total_tokens: int | None,
    provider_id: str | None,
) -> int:
    """
    按「基础单价 × 模型倍率 × Provider 结算系数 × token 数」计算应扣积分。
    """
    base_per_1k = int(getattr(settings, "credits_base_per_1k_tokens", 0))
    if base_per_1k <= 0:
        return 0
    if total_tokens is None or total_tokens <= 0:
        return 0

    model_multiplier = _load_multiplier_for_model(db, model_name)
    provider_factor = _load_provider_factor(db, provider_id)
    raw_cost = (total_tokens / 1000.0) * base_per_1k * model_multiplier * provider_factor
    cost = int(math.ceil(raw_cost))
    if cost <= 0:
        cost = 1
    return cost


def _create_transaction(
    db: Session,
    *,
    account: CreditAccount,
    user_id: UUID,
    api_key_id: UUID | None,
    amount: int,
    reason: str,
    description: str | None,
    model_name: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
) -> CreditTransaction:
    tx = CreditTransaction(
        account_id=account.id,
        user_id=user_id,
        api_key_id=api_key_id,
        amount=amount,
        reason=reason,
        description=description,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    db.add(tx)
    return tx


def apply_manual_delta(
    db: Session,
    *,
    user_id: UUID,
    api_key_id: UUID | None = None,
    amount: int,
    reason: str = "adjust",
    description: str | None = None,
) -> CreditAccount:
    """
    管理端使用：给用户积分账户充值或调整余额。

    amount 为正数时表示充值，负数表示扣减。
    """
    if amount == 0:
        raise ValueError("amount 不能为 0")

    account = get_or_create_account_for_user(db, user_id)
    account.balance = int(account.balance) + int(amount)
    _create_transaction(
        db,
        account=account,
        user_id=user_id,
        api_key_id=api_key_id,
        amount=amount,
        reason=reason,
        description=description,
        model_name=None,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
    )
    db.commit()
    db.refresh(account)
    return account


def record_chat_completion_usage(
    db: Session,
    *,
    user_id: UUID,
    api_key_id: UUID | None,
    model_name: str | None,
    provider_id: str | None,
    payload: dict[str, Any] | None,
    is_stream: bool = False,
    reason: str | None = None,
) -> int:
    """
    根据响应 payload 中的 usage 字段记录一次调用消耗，并扣减积分。

    返回本次扣减的积分数（可能为 0）。
    """
    if payload is None or not isinstance(payload, dict):
        return 0

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        # 某些厂商在流式模式下仅在最终 chunk 给 usage，或没有 usage 字段。
        return 0

    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        try:
            total_tokens = int(input_tokens) + int(output_tokens)
        except Exception:
            total_tokens = None

    if total_tokens is None:
        return 0

    account = get_or_create_account_for_user(db, user_id)
    # 1) 优先尝试使用 provider+model 维度的定价（如果已在 provider_models.pricing 中配置）。
    #
    # 约定：
    # - pricing.input / pricing.output 表示每 1000 tokens 扣除的积分数；
    # - 若任一价格存在并且 usage 中有对应 token 统计，则使用明细价计算；
    # - 仍然会叠加 ModelBillingConfig.multiplier 与 Provider.billing_factor，方便做全局调整。
    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=model_name
    )

    cost: int
    if (input_price is not None or output_price is not None) and (
        input_tokens is not None or output_tokens is not None
    ):
        try:
            model_multiplier = _load_multiplier_for_model(db, model_name)
            provider_factor = _load_provider_factor(db, provider_id)

            raw_cost = 0.0
            if input_tokens is not None and input_price is not None:
                raw_cost += (int(input_tokens) / 1000.0) * input_price
            if output_tokens is not None and output_price is not None:
                raw_cost += (int(output_tokens) / 1000.0) * output_price

            raw_cost *= model_multiplier * provider_factor
            cost = int(math.ceil(raw_cost))
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to compute credit cost with ProviderModel.pricing "
                "for provider=%r model=%r; falling back to legacy pricing",
                provider_id,
                model_name,
            )
            cost = _compute_cost_credits(
                db=db,
                model_name=model_name,
                total_tokens=int(total_tokens),
                provider_id=provider_id,
            )
    else:
        # 2) 未配置单独价格时，退回到以逻辑模型维度为主的旧计费规则。
        cost = _compute_cost_credits(
            db=db,
            model_name=model_name,
            total_tokens=int(total_tokens),
            provider_id=provider_id,
        )

    if cost <= 0:
        return 0

    account.balance = int(account.balance) - cost
    tx_reason = reason or ("stream_usage" if is_stream else "usage")
    _create_transaction(
        db,
        account=account,
        user_id=user_id,
        api_key_id=api_key_id,
        amount=-cost,
        reason=tx_reason,
        description=None,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    db.commit()
    db.refresh(account)
    logger.info(
        "Recorded credit usage for user=%s model=%r total_tokens=%s cost=%s balance_after=%s",
        user_id,
        model_name,
        total_tokens,
        cost,
        account.balance,
    )
    return cost


def record_streaming_request(
    db: Session,
    *,
    user_id: UUID,
    api_key_id: UUID | None,
    model_name: str | None,
    provider_id: str | None,
    payload: dict[str, Any],
) -> int:
    """
    对流式请求进行粗略扣费：
    - 优先使用 max_tokens / max_tokens_to_sample / max_output_tokens；
    - 若没有，则使用 STREAMING_MIN_TOKENS 作为近似 token 数。
    """
    approx_tokens: int | None = None
    for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
        value = payload.get(key)
        if isinstance(value, int) and value > 0:
            approx_tokens = value
            break

    if approx_tokens is None:
        approx_tokens = int(getattr(settings, "streaming_min_tokens", 0) or 0)

    if approx_tokens <= 0:
        return 0

    account = get_or_create_account_for_user(db, user_id)

    # 优先尝试使用 provider+model 维度的定价。
    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=model_name
    )

    cost: int
    if input_price is not None or output_price is not None:
        try:
            model_multiplier = _load_multiplier_for_model(db, model_name)
            provider_factor = _load_provider_factor(db, provider_id)
            # 流式场景只有一个预估 token 数，缺少输入/输出拆分；
            # 为了简单且偏保守，这里全部按 output 单价计费，若只配置了 input 单价则退回 input。
            per_1k = output_price if output_price is not None else input_price
            raw_cost = (approx_tokens / 1000.0) * per_1k * model_multiplier * provider_factor
            cost = int(math.ceil(raw_cost))
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to compute streaming credit cost with ProviderModel.pricing "
                "for provider=%r model=%r; falling back to legacy pricing",
                provider_id,
                model_name,
            )
            cost = _compute_cost_credits(
                db=db,
                model_name=model_name,
                total_tokens=approx_tokens,
                provider_id=provider_id,
            )
    else:
        cost = _compute_cost_credits(
            db=db,
            model_name=model_name,
            total_tokens=approx_tokens,
            provider_id=provider_id,
        )
    if cost <= 0:
        return 0

    account.balance = int(account.balance) - cost
    _create_transaction(
        db,
        account=account,
        user_id=user_id,
        api_key_id=api_key_id,
        amount=-cost,
        reason="stream_estimate",
        description="流式请求预估扣费",
        model_name=model_name,
        input_tokens=None,
        output_tokens=None,
        total_tokens=approx_tokens,
    )
    db.commit()
    db.refresh(account)
    logger.info(
        "Recorded streaming credit usage for user=%s model=%r approx_tokens=%s cost=%s balance_after=%s",
        user_id,
        model_name,
        approx_tokens,
        cost,
        account.balance,
    )
    return cost


__all__ = [
    "InsufficientCreditsError",
    "apply_manual_delta",
    "ensure_account_usable",
    "get_or_create_account_for_user",
    "record_chat_completion_usage",
    "record_streaming_request",
]
