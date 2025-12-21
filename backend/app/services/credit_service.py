from __future__ import annotations

import datetime as dt
import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import (
    CreditAccount,
    CreditAutoTopupRule,
    CreditTransaction,
    ModelBillingConfig,
    Provider,
    ProviderModel,
)
from app.schemas.notification import NotificationCreateRequest
from app.services.metrics_service import record_provider_token_usage
from app.services.notification_service import create_notification
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


def _load_provider_transport(db: Session, provider_id: str | None) -> str:
    if not provider_id:
        return "http"
    try:
        value = (
            db.execute(select(Provider.transport).where(Provider.provider_id == provider_id))
            .scalars()
            .first()
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to load Provider.transport for provider_id=%r", provider_id)
        return "http"
    if not value:
        return "http"
    try:
        return str(value)
    except Exception:
        return "http"


def estimate_request_cost_credits(
    db: Session,
    *,
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    request_payload: dict[str, Any] | None,
) -> int | None:
    """
    基于 request_payload 对一次调用进行“保守”的积分成本预估（不做扣费）。

    约定与扣费逻辑保持一致：
    - tokens：优先使用 max_tokens / max_tokens_to_sample / max_output_tokens 粗略估算；
    - 价格：优先使用 provider_models.pricing（input/output 单价）；当缺少 input/output 拆分时整体按 output 计费；
    - 叠加：logical_model 的 multiplier（ModelBillingConfig）与 Provider.billing_factor。

    返回：
    - 预估成本（int，向上取整）；
    - 若无法预估（缺少 tokens 或 pricing），返回 None。
    """
    if not isinstance(request_payload, dict):
        return None

    approx_tokens: int | None = None
    for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
        value = request_payload.get(key)
        if isinstance(value, int) and value > 0:
            approx_tokens = value
            break

    if approx_tokens is None:
        return None

    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=provider_model_id
    )
    if input_price is None and output_price is None:
        return None

    per_1k = output_price if output_price is not None else input_price
    if per_1k is None:
        return None

    try:
        model_multiplier = _load_multiplier_for_model(db, logical_model_name)
        provider_factor = _load_provider_factor(db, provider_id)
        raw_cost = (int(approx_tokens) / 1000.0) * float(per_1k) * model_multiplier * provider_factor
        cost = int(math.ceil(raw_cost))
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to estimate credit cost for provider=%r model=%r logical=%r",
            provider_id,
            provider_model_id,
            logical_model_name,
        )
        return None

    if cost < 0:
        return None
    return cost


def compute_chat_completion_cost_credits(
    db: Session,
    *,
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    response_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None = None,
) -> int | None:
    """
    纯计算：根据响应 usage（或请求侧保守估算）计算一次调用的积分成本（不扣费、不写流水）。

    - 优先使用 response_payload["usage"]；
    - 若 usage 不存在，则回退到 request_payload 的 max_tokens 等字段；
    - 定价、倍率与 record_chat_completion_usage 保持一致。
    """
    usage: dict[str, Any] | None = None
    if isinstance(response_payload, dict):
        raw_usage = response_payload.get("usage")
        if isinstance(raw_usage, dict):
            usage = raw_usage

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    if isinstance(usage, dict):
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")

        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            try:
                total_tokens = int(input_tokens) + int(output_tokens)
            except Exception:
                total_tokens = None

    if total_tokens is None and isinstance(request_payload, dict):
        approx_tokens: int | None = None
        for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
            value = request_payload.get(key)
            if isinstance(value, int) and value > 0:
                approx_tokens = value
                break
        if approx_tokens is not None and approx_tokens > 0:
            total_tokens = approx_tokens
            input_tokens = None
            output_tokens = None

    if total_tokens is None:
        return None

    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=provider_model_id
    )
    if input_price is None and output_price is None:
        return None

    try:
        model_multiplier = _load_multiplier_for_model(db, logical_model_name)
        provider_factor = _load_provider_factor(db, provider_id)

        raw_cost = 0.0
        if input_tokens is not None or output_tokens is not None:
            if input_tokens is not None and input_price is not None:
                raw_cost += (int(input_tokens) / 1000.0) * float(input_price)
            if output_tokens is not None and output_price is not None:
                raw_cost += (int(output_tokens) / 1000.0) * float(output_price)
        else:
            per_1k = output_price if output_price is not None else input_price
            if per_1k is None:
                return None
            raw_cost = (int(total_tokens) / 1000.0) * float(per_1k)

        raw_cost *= float(model_multiplier) * float(provider_factor)
        cost = int(math.ceil(raw_cost))
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to compute chat completion credit cost for provider=%r model=%r logical=%r",
            provider_id,
            provider_model_id,
            logical_model_name,
        )
        return None

    if cost < 0:
        return None
    return cost


def estimate_streaming_precharge_cost_credits(
    db: Session,
    *,
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    request_payload: dict[str, Any] | None,
) -> int | None:
    """
    纯计算：按流式预扣费口径对一次请求做保守估算（不扣费、不写流水）。

    - 优先使用 max_tokens / max_tokens_to_sample / max_output_tokens；
    - 若缺失，则回退到 STREAMING_MIN_TOKENS；
    - 定价、倍率与 record_streaming_request 保持一致。
    """
    if not isinstance(request_payload, dict):
        return None

    approx_tokens: int | None = None
    for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
        value = request_payload.get(key)
        if isinstance(value, int) and value > 0:
            approx_tokens = value
            break

    if approx_tokens is None:
        approx_tokens = int(getattr(settings, "streaming_min_tokens", 0) or 0)

    if approx_tokens <= 0:
        return None

    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=provider_model_id
    )
    if input_price is None and output_price is None:
        return None

    try:
        model_multiplier = _load_multiplier_for_model(db, logical_model_name)
        provider_factor = _load_provider_factor(db, provider_id)
        per_1k = output_price if output_price is not None else input_price
        if per_1k is None:
            return None
        raw_cost = (int(approx_tokens) / 1000.0) * float(per_1k) * float(model_multiplier) * float(provider_factor)
        cost = int(math.ceil(raw_cost))
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to estimate streaming precharge credit cost for provider=%r model=%r logical=%r",
            provider_id,
            provider_model_id,
            logical_model_name,
        )
        return None

    if cost < 0:
        return None
    return cost



def _create_transaction(
    db: Session,
    *,
    account: CreditAccount,
    user_id: UUID,
    api_key_id: UUID | None,
    provider_id: str | None,
    provider_model_id: str | None,
    amount: int,
    reason: str,
    description: str | None,
    model_name: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    idempotency_key: str | None = None,
) -> CreditTransaction:
    tx = CreditTransaction(
        account_id=account.id,
        user_id=user_id,
        api_key_id=api_key_id,
        provider_id=provider_id,
        provider_model_id=provider_model_id,
        amount=amount,
        idempotency_key=idempotency_key,
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
        provider_id=None,
        provider_model_id=None,
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
    logger.info(
        "Applied manual credit delta for user=%s: amount=%s reason=%r description=%r balance_after=%s",
        user_id,
        amount,
        reason,
        description,
        account.balance,
    )
    return account


def get_auto_topup_rule_for_user(
    db: Session,
    user_id: UUID,
) -> CreditAutoTopupRule | None:
    """
    获取指定用户的自动充值规则（若未配置则返回 None）。
    """
    return (
        db.execute(
            select(CreditAutoTopupRule).where(
                CreditAutoTopupRule.user_id == user_id
            )
        )
        .scalars()
        .first()
    )


def upsert_auto_topup_rule(
    db: Session,
    *,
    user_id: UUID,
    min_balance_threshold: int,
    target_balance: int,
    is_active: bool = True,
) -> CreditAutoTopupRule:
    """
    为用户创建或更新自动充值规则。

    - 当积分余额低于 min_balance_threshold 时，将自动补至 target_balance；
    - is_active 控制规则是否生效。
    """
    if min_balance_threshold <= 0 or target_balance <= 0:
        raise ValueError("min_balance_threshold 与 target_balance 必须为正整数")

    rule = get_auto_topup_rule_for_user(db, user_id)
    if rule is None:
        rule = CreditAutoTopupRule(
            user_id=user_id,
            min_balance_threshold=min_balance_threshold,
            target_balance=target_balance,
            is_active=is_active,
        )
        db.add(rule)
    else:
        rule.min_balance_threshold = min_balance_threshold
        rule.target_balance = target_balance
        rule.is_active = is_active

    db.commit()
    db.refresh(rule)
    return rule


def disable_auto_topup_for_user(db: Session, *, user_id: UUID) -> None:
    """
    关闭指定用户的自动充值规则（若不存在则忽略）。
    """
    rule = get_auto_topup_rule_for_user(db, user_id)
    if rule is None:
        return

    rule.is_active = False
    db.commit()


def run_daily_auto_topups(db: Session) -> int:
    """
    扫描所有启用的自动充值规则，对余额不足的账户进行充值。

    规则：
    - 仅处理 is_active=True 的规则；
    - 当当前余额 < min_balance_threshold 且 < target_balance 时，
      通过 apply_manual_delta 将余额调整为 target_balance；
    - 充值记录的 reason 固定为 \"auto_daily_topup\"。

    返回本次实际执行充值的账户数量。
    """
    rules = (
        db.execute(
            select(CreditAutoTopupRule).where(
                CreditAutoTopupRule.is_active.is_(True)
            )
        )
        .scalars()
        .all()
    )

    processed = 0
    for rule in rules:
        account = get_or_create_account_for_user(db, rule.user_id)
        current_balance = int(account.balance)

        if current_balance >= rule.min_balance_threshold:
            continue
        if current_balance >= rule.target_balance:
            # 若目标值不高于当前余额，则无需调整。
            continue

        delta = int(rule.target_balance) - current_balance
        try:
            apply_manual_delta(
                db,
                user_id=rule.user_id,
                amount=delta,
                reason="auto_daily_topup",
                description="自动每日积分充值",
            )
            processed += 1
            # 推送通知提醒用户
            try:
                create_notification(
                    db,
                    NotificationCreateRequest(
                        title="积分已自动充值",
                        content=(
                            f"系统检测到您的积分不足，已自动为账户充值 {delta} 积分，"
                            f"当前目标余额：{rule.target_balance}。"
                        ),
                        level="info",
                        target_type="users",
                        target_user_ids=[rule.user_id],
                    ),
                    creator_id=None,
                )
            except Exception:  # pragma: no cover - 通知失败不影响扣费流程
                logger.exception(
                    "Failed to send auto-topup notification for user %s", rule.user_id
                )
        except Exception:  # pragma: no cover - 防御性日志
            logger.exception(
                "Failed to apply auto topup for user=%s rule_id=%s",
                rule.user_id,
                rule.id,
            )

    return processed


def record_chat_completion_usage(
    db: Session,
    *,
    user_id: UUID,
    api_key_id: UUID | None,
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    response_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None = None,
    is_stream: bool = False,
    reason: str | None = None,
    idempotency_key: str | None = None,
    occurred_at: dt.datetime | None = None,
) -> int:
    """
    根据响应 payload 中的 usage 字段记录一次调用消耗，并扣减积分。

    优先使用 Provider+Model 维度的定价（provider_models.pricing），并在此基础上叠加：
    - 逻辑模型倍率：ModelBillingConfig.multiplier（按 logical_model_name 查找）；
    - Provider 结算系数：Provider.billing_factor。

    当上游未返回 usage 时，若提供了 request_payload，则尝试从
    max_tokens / max_tokens_to_sample / max_output_tokens 粗略估算一次总 token 数；
    若仍无法估算，则不做扣费（返回 0）。

    返回本次扣减的积分数（可能为 0）。
    """
    if response_payload is None or not isinstance(response_payload, dict):
        # 无结构化响应时，仅能依赖请求侧的粗略估算；此处交由后续逻辑处理。
        usage: dict[str, Any] | None = None
    else:
        usage = response_payload.get("usage")

    if not isinstance(usage, dict):
        # 某些厂商在流式模式下仅在最终 chunk 给 usage，或没有 usage 字段。
        usage = None

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    if isinstance(usage, dict):
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")

        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            try:
                total_tokens = int(input_tokens) + int(output_tokens)
            except Exception:
                total_tokens = None

    # usage 中无法获得 total_tokens 时，尝试基于请求参数做一次保守预估。
    if total_tokens is None and isinstance(request_payload, dict):
        approx_tokens: int | None = None
        for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
            value = request_payload.get(key)
            if isinstance(value, int) and value > 0:
                approx_tokens = value
                break

        if approx_tokens is not None and approx_tokens > 0:
            total_tokens = approx_tokens
            # 在只有预估总量时，输入 / 输出无法拆分，这里保持为 None，后续按总量计费。
            input_tokens = None
            output_tokens = None

    if total_tokens is None:
        return 0

    try:
        transport = _load_provider_transport(db, provider_id)
        estimated = input_tokens is None and output_tokens is None
        record_provider_token_usage(
            db,
            provider_id=provider_id or "",
            logical_model=logical_model_name or "",
            transport=transport,
            is_stream=bool(is_stream),
            user_id=user_id,
            api_key_id=api_key_id,
            occurred_at=occurred_at,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated=estimated,
        )
    except Exception:  # pragma: no cover - 指标失败不影响扣费
        logger.exception(
            "Failed to record token usage for user=%s provider=%s model=%s",
            user_id,
            provider_id,
            logical_model_name,
        )

    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=provider_model_id
    )

    if input_price is None and output_price is None:
        logger.info(
            "Skip credit deduction due to missing provider pricing: provider=%r model=%r",
            provider_id,
            provider_model_id,
        )
        return 0

    try:
        # 逻辑模型倍率始终按 logical_model_name 维度配置，避免与 Provider 模型 ID 混淆。
        model_multiplier = _load_multiplier_for_model(db, logical_model_name)
        provider_factor = _load_provider_factor(db, provider_id)

        raw_cost = 0.0
        if input_tokens is not None or output_tokens is not None:
            # 具备输入 / 输出拆分的 usage 时，分别按 input/output 单价计费。
            if input_tokens is not None and input_price is not None:
                raw_cost += (int(input_tokens) / 1000.0) * input_price
            if output_tokens is not None and output_price is not None:
                raw_cost += (int(output_tokens) / 1000.0) * output_price
        else:
            # 仅有总 token 数（例如基于请求 max_tokens 估算）时，
            # 为简单且偏保守，整体按 output 单价计费；若只配置了 input 单价则退回 input。
            per_1k = output_price if output_price is not None else input_price
            raw_cost = (int(total_tokens) / 1000.0) * per_1k

        raw_cost *= model_multiplier * provider_factor
        cost = int(math.ceil(raw_cost))
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to compute credit cost with ProviderModel.pricing for provider=%r model=%r",
            provider_id,
            provider_model_id,
        )
        return 0

    if cost <= 0:
        return 0

    if idempotency_key:
        existing = (
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.idempotency_key == idempotency_key
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return 0

    account = get_or_create_account_for_user(db, user_id)

    account.balance = int(account.balance) - cost
    tx_reason = reason or ("stream_usage" if is_stream else "usage")
    _create_transaction(
        db,
        account=account,
        user_id=user_id,
        api_key_id=api_key_id,
        provider_id=provider_id,
        provider_model_id=provider_model_id,
        amount=-cost,
        idempotency_key=idempotency_key,
        reason=tx_reason,
        description=None,
        model_name=logical_model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0
    db.refresh(account)
    logger.info(
        "Recorded credit usage for user=%s model=%r total_tokens=%s cost=%s balance_after=%s",
        user_id,
        logical_model_name,
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
    logical_model_name: str | None,
    provider_id: str | None,
    provider_model_id: str | None,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
) -> int:
    """
    对流式请求进行粗略扣费：
    - 优先使用 max_tokens / max_tokens_to_sample / max_output_tokens；
    - 若没有，则使用 STREAMING_MIN_TOKENS 作为近似 token 数。
    """
    if not getattr(settings, "enable_streaming_precharge", False):
        # 预扣开关关闭时（默认），直接跳过，等待最终 usage 才扣费。
        return 0

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

    # 优先尝试使用 provider+model 维度的定价。
    input_price, output_price = _load_provider_model_pricing(
        db, provider_id=provider_id, model_name=provider_model_id
    )

    if input_price is None and output_price is None:
        logger.info(
            "Skip streaming credit precharge due to missing provider pricing: provider=%r model=%r",
            provider_id,
            provider_model_id,
        )
        return 0

    try:
        # 流式场景下倍率同样按逻辑模型维度配置。
        model_multiplier = _load_multiplier_for_model(db, logical_model_name)
        provider_factor = _load_provider_factor(db, provider_id)
        # 流式场景只有一个预估 token 数，缺少输入/输出拆分；
        # 为了简单且偏保守，这里全部按 output 单价计费，若只配置了 input 单价则退回 input。
        per_1k = output_price if output_price is not None else input_price
        raw_cost = (approx_tokens / 1000.0) * per_1k * model_multiplier * provider_factor
        cost = int(math.ceil(raw_cost))
    except Exception:  # pragma: no cover - 防御性日志
        logger.exception(
            "Failed to compute streaming credit cost with ProviderModel.pricing for provider=%r model=%r",
            provider_id,
            provider_model_id,
        )
        return 0

    if cost <= 0:
        return 0

    if idempotency_key:
        existing = (
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.idempotency_key == idempotency_key
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return 0

    account = get_or_create_account_for_user(db, user_id)
    account.balance = int(account.balance) - cost
    _create_transaction(
        db,
        account=account,
        user_id=user_id,
        api_key_id=api_key_id,
        provider_id=provider_id,
        provider_model_id=provider_model_id,
        amount=-cost,
        idempotency_key=idempotency_key,
        reason="stream_estimate",
        description="流式请求预估扣费",
        model_name=logical_model_name,
        input_tokens=None,
        output_tokens=None,
        total_tokens=approx_tokens,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0
    db.refresh(account)
    logger.info(
        "Recorded streaming credit usage for user=%s model=%r approx_tokens=%s cost=%s balance_after=%s",
        user_id,
        logical_model_name,
        approx_tokens,
        cost,
        account.balance,
    )
    return cost


__all__ = [
    "InsufficientCreditsError",
    "apply_manual_delta",
    "compute_chat_completion_cost_credits",
    "disable_auto_topup_for_user",
    "ensure_account_usable",
    "estimate_streaming_precharge_cost_credits",
    "get_auto_topup_rule_for_user",
    "get_or_create_account_for_user",
    "record_chat_completion_usage",
    "record_streaming_request",
    "run_daily_auto_topups",
    "upsert_auto_topup_rule",
]
