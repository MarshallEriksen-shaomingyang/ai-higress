from __future__ import annotations

from datetime import datetime
from typing import List
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

    user_ids: List[UUID] = Field(
        ...,
        min_length=1,
        description="需要应用自动充值规则的用户 ID 列表",
    )


class CreditAutoTopupBatchResponse(BaseModel):
    """
    批量配置自动充值规则的结果。
    """

    updated_count: int = Field(..., description="实际创建或更新的规则数量")
    configs: List[CreditAutoTopupConfigResponse] = Field(
        default_factory=list,
        description="被创建/更新后的规则明细列表",
    )


__all__ = [
    "CreditAccountResponse",
    "CreditTopupRequest",
    "CreditTransactionResponse",
    "CreditAutoTopupConfig",
    "CreditAutoTopupConfigResponse",
    "CreditAutoTopupBatchRequest",
    "CreditAutoTopupBatchResponse",
]
