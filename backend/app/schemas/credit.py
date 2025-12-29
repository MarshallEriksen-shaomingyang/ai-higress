from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreditAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    balance: int = Field(..., description="当前积分余额")
    daily_limit: int | None = Field(
        default=None,
        description="每日最大可消耗的积分（为空表示不限制）",
    )
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditTransactionResponse(BaseModel):
    id: UUID
    account_id: UUID
    user_id: UUID
    api_key_id: UUID | None = None
    amount: int = Field(..., description="积分变动值；正数为增加，负数为扣减")
    reason: str = Field(..., description="变动原因，如 usage / stream_estimate / admin_topup 等")
    description: str | None = None
    model_name: str | None = None
    provider_id: str | None = Field(
        default=None,
        description="本次流水涉及的 Provider ID，用于前端做聚合统计",
    )
    provider_model_id: str | None = Field(
        default=None,
        description="Provider 侧的模型 ID（若可用）",
    )
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditTopupRequest(BaseModel):
    amount: int = Field(..., gt=0, description="要增加的积分数量（必须为正数）")
    description: str | None = Field(
        default=None,
        description="本次充值或调整的备注说明",
    )


class CreditGrantRequest(BaseModel):
    amount: int = Field(..., gt=0, description="要增加的积分数量（必须为正数）")
    reason: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="入账来源标识（建议：sign_in / redeem_code / promo 等，最长 32 字符）",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        description="备注说明（最长 255 字符）",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=80,
        description="幂等键：同一个 key 只会入账一次（建议包含活动/用户/日期等信息）",
    )


class CreditGrantResponse(BaseModel):
    applied: bool = Field(
        ...,
        description="本次是否实际入账；当 idempotency_key 重复时为 false",
    )
    account: CreditAccountResponse
    transaction: CreditTransactionResponse | None = Field(
        default=None,
        description="本次入账对应的流水（幂等重复时返回已存在的流水）",
    )


class CreditGrantTokenIssueRequest(BaseModel):
    user_id: UUID | None = Field(
        default=None,
        description="限制仅该用户可兑换；为空表示不限制（通常用于兑换码）",
    )
    amount: int = Field(..., gt=0, description="要增加的积分数量（必须为正数）")
    reason: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="入账来源标识（建议：sign_in / redeem_code / promo 等，最长 32 字符）",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        description="备注说明（最长 255 字符）",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=80,
        description="可选幂等键：相同 key 只允许兑换一次；为空则自动生成随机 key",
    )
    expires_in_seconds: int = Field(
        86400,
        ge=60,
        le=30 * 86400,
        description="token 有效期（秒），默认 1 天，最长 30 天",
    )


class CreditGrantTokenIssueResponse(BaseModel):
    token: str = Field(..., description="签发的兑换 token（HS256）")
    expires_at: datetime = Field(..., description="过期时间（UTC）")


class CreditGrantTokenRedeemRequest(BaseModel):
    token: str = Field(..., min_length=10, description="兑换 token")


class CreditAutoTopupConfig(BaseModel):
    """
    管理员配置的自动充值规则。

    - 当用户余额低于 min_balance_threshold 时，
      系统会自动将余额补至 target_balance。
    """

    min_balance_threshold: int = Field(
        ...,
        gt=0,
        description="触发自动充值的余额阈值（当余额低于该值时触发，必须为正整数）",
    )
    target_balance: int = Field(
        ...,
        gt=0,
        description="自动充值后希望达到的余额（必须为正整数且大于触发阈值）",
    )
    is_active: bool = Field(
        True,
        description="是否启用该自动充值规则",
    )


class CreditAutoTopupConfigResponse(CreditAutoTopupConfig):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditAutoTopupBatchRequest(CreditAutoTopupConfig):
    """
    批量为多个用户配置自动充值规则。

    - user_ids 为要应用该规则的用户列表；
    - 其他字段沿用 CreditAutoTopupConfig 的含义。
    """

    user_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="需要应用自动充值规则的用户 ID 列表",
    )


class CreditAutoTopupBatchResponse(BaseModel):
    """
    批量配置自动充值规则的结果。
    """

    updated_count: int = Field(..., description="实际创建或更新的规则数量")
    configs: list[CreditAutoTopupConfigResponse] = Field(
        default_factory=list,
        description="被创建/更新后的规则明细列表",
    )


class CreditConsumptionSummary(BaseModel):
    """
    仪表盘概览页使用的积分消耗概要信息。
    """

    time_range: str
    start_at: datetime | None
    end_at: datetime
    spent_credits: int = Field(..., description="统计窗口内总消耗积分")
    spent_credits_prev: int | None = Field(
        None,
        description="上一对比周期的积分消耗（若可用）",
    )
    transactions: int = Field(..., description="统计窗口内的消耗类流水数量")
    avg_daily_spent: float = Field(
        ...,
        description="按窗口长度折算的日均消耗；无记录时为 0",
    )
    balance: int = Field(..., description="当前积分余额")
    projected_days_left: float | None = Field(
        None,
        description="若保持当前日均消耗，预计剩余可用天数；日均为 0 时返回 null",
    )


class CreditProviderUsageItem(BaseModel):
    provider_id: str
    provider_name: str | None = None
    total_spent: int = Field(..., description="该 Provider 对应的积分消耗")
    transaction_count: int = Field(..., description="命中的流水条数")
    percentage: float = Field(
        ...,
        description="相对于统计窗口总消耗的占比，范围 [0,1]",
    )
    last_transaction_at: datetime | None = Field(
        None,
        description="最近一次涉及该 Provider 的消费时间",
    )


class CreditProviderUsageResponse(BaseModel):
    time_range: str
    total_spent: int
    items: list[CreditProviderUsageItem] = Field(default_factory=list)


class CreditUsageTimeseriesPoint(BaseModel):
    window_start: datetime
    spent_credits: int


class CreditUsageTimeseriesResponse(BaseModel):
    time_range: str
    bucket: str
    points: list[CreditUsageTimeseriesPoint] = Field(default_factory=list)


__all__ = [
    "CreditAccountResponse",
    "CreditAutoTopupBatchRequest",
    "CreditAutoTopupBatchResponse",
    "CreditAutoTopupConfig",
    "CreditAutoTopupConfigResponse",
    "CreditConsumptionSummary",
    "CreditGrantRequest",
    "CreditGrantResponse",
    "CreditGrantTokenIssueRequest",
    "CreditGrantTokenIssueResponse",
    "CreditGrantTokenRedeemRequest",
    "CreditProviderUsageItem",
    "CreditProviderUsageResponse",
    "CreditTopupRequest",
    "CreditTransactionResponse",
    "CreditUsageTimeseriesPoint",
    "CreditUsageTimeseriesResponse",
]
