from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CreditAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    用户积分账户。

    - 与 User 为 1:1 关系（通过 user_id 唯一约束）；
    - balance 使用整数表示积分数量；
    - status 保留为扩展字段，支持后续手动冻结账户等场景。
    """

    __tablename__ = "credit_accounts"

    user_id: Mapped[UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    balance: Mapped[int] = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    daily_limit: Mapped[int | None] = Column(Integer, nullable=True)
    status: Mapped[str] = Column(
        String(16),
        nullable=False,
        server_default=text("'active'"),
        default="active",
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="credit_account",
    )
    transactions: Mapped[list[CreditTransaction]] = relationship(
        "CreditTransaction",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CreditTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    积分变动流水。

    - amount 为整数，正数代表增加积分，负数代表扣减积分；
    - reason 记录来源：usage/stream_usage/admin_topup/adjust 等；
    - token 相关字段用于审计和对账，后续前端可做可视化。
    """

    __tablename__ = "credit_transactions"

    account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("credit_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[UUID | None] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[int] = Column(Integer, nullable=False)
    # 用于幂等扣费：同一个 idempotency_key 只允许生成一条流水（通过 DB 唯一索引保障）。
    idempotency_key: Mapped[str | None] = Column(String(80), nullable=True, index=True)
    reason: Mapped[str] = Column(
        String(32),
        nullable=False,
        server_default=text("'usage'"),
        default="usage",
    )
    description: Mapped[str | None] = Column(String(255), nullable=True)
    model_name: Mapped[str | None] = Column(String(100), nullable=True)
    provider_id: Mapped[str | None] = Column(
        String(50),
        ForeignKey("providers.provider_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider_model_id: Mapped[str | None] = Column(String(100), nullable=True)

    # 可选：记录本次调用的 token 统计，便于后续报表和排查。
    input_tokens: Mapped[int | None] = Column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = Column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = Column(Integer, nullable=True)

    account: Mapped[CreditAccount] = relationship(
        "CreditAccount",
        back_populates="transactions",
    )
    user: Mapped[User] = relationship("User")
    api_key: Mapped[APIKey] = relationship("APIKey")


class ModelBillingConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    逻辑模型计费配置。

    - model_name 一般对应 logical_model.logical_id 或客户端使用的 model 名；
    - multiplier 为倍率系数，会与 ProviderModel.pricing（input/output 单价）
      以及 Provider.billing_factor 一同决定最终扣费金额。
    """

    __tablename__ = "model_billing_configs"

    model_name: Mapped[str] = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    multiplier: Mapped[float] = Column(Float, nullable=False, server_default=text("1.0"))
    description: Mapped[str | None] = Column(String(255), nullable=True)
    is_active: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
        default=True,
    )


class CreditAutoTopupRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    自动积分充值规则。

    - 针对单个用户配置，当账户余额低于 min_balance_threshold 时，
      定时任务会将余额调整为 target_balance；
    - 仅当 is_active=True 时生效。
    """

    __tablename__ = "credit_auto_topup_rules"

    user_id: Mapped[UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    min_balance_threshold: Mapped[int] = Column(Integer, nullable=False)
    target_balance: Mapped[int] = Column(Integer, nullable=False)
    is_active: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
        default=True,
    )


__all__ = [
    "CreditAccount",
    "CreditAutoTopupRule",
    "CreditTransaction",
    "ModelBillingConfig",
]
