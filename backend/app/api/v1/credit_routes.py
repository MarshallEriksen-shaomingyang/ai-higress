"""
积分账户与流水相关路由。

设计目标：
- 普通用户可以查询自己的积分余额与近期流水；
- 管理员可以为指定用户充值/调整积分；
- 具体扣费逻辑在 app.services.credit_service 中实现，路由层只做薄封装。
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import CreditAccount, CreditTransaction
from app.schemas import (
    CreditAccountResponse,
    CreditAutoTopupConfig,
    CreditAutoTopupConfigResponse,
    CreditAutoTopupBatchRequest,
    CreditAutoTopupBatchResponse,
    CreditTopupRequest,
    CreditTransactionResponse,
)
from app.services.credit_service import (
    apply_manual_delta,
    disable_auto_topup_for_user,
    get_auto_topup_rule_for_user,
    get_or_create_account_for_user,
    upsert_auto_topup_rule,
)

router = APIRouter(
    tags=["credits"],
    prefix="/v1/credits",
    dependencies=[Depends(require_jwt_token)],
)


@router.get("/me", response_model=CreditAccountResponse)
def get_my_credit_account(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditAccountResponse:
    """
    获取当前登录用户的积分账户信息。

    若账户不存在，则按配置自动初始化一个新的账户。
    """
    account = get_or_create_account_for_user(db, UUID(current_user.id))
    return CreditAccountResponse.model_validate(account)


@router.get("/me/transactions", response_model=List[CreditTransactionResponse])
def list_my_transactions(
    limit: int = Query(50, ge=1, le=100, description="返回的最大记录数"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> List[CreditTransactionResponse]:
    """
    分页返回当前用户的积分流水记录（按时间倒序）。
    """
    # 通过 user_id 维度过滤，避免暴露其他用户数据。
    q = (
        db.query(CreditTransaction)
        .join(CreditAccount, CreditTransaction.account_id == CreditAccount.id)
        .filter(CreditAccount.user_id == UUID(current_user.id))
        .order_by(CreditTransaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = q.all()
    return [CreditTransactionResponse.model_validate(item) for item in items]


@router.post(
    "/admin/users/{user_id}/topup",
    response_model=CreditAccountResponse,
    status_code=status.HTTP_200_OK,
)
def admin_topup_user_credits(
    user_id: UUID,
    payload: CreditTopupRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditAccountResponse:
    """
    管理员为指定用户充值/增加积分。

    仅当 current_user.is_superuser 为 True 时允许调用。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以调整用户积分")

    account = apply_manual_delta(
        db,
        user_id=user_id,
        amount=payload.amount,
        reason="admin_topup",
        description=payload.description,
    )
    return CreditAccountResponse.model_validate(account)


@router.get(
    "/admin/users/{user_id}/auto-topup",
    response_model=CreditAutoTopupConfigResponse | None,
)
def get_user_auto_topup_config(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditAutoTopupConfigResponse | None:
    """
    获取指定用户的自动充值配置。

    若未配置则返回 null。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以查看或修改自动充值配置")

    rule = get_auto_topup_rule_for_user(db, user_id)
    if rule is None:
        return None
    return CreditAutoTopupConfigResponse.model_validate(rule)


@router.put(
    "/admin/users/{user_id}/auto-topup",
    response_model=CreditAutoTopupConfigResponse,
)
def upsert_user_auto_topup_config(
    user_id: UUID,
    payload: CreditAutoTopupConfig,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditAutoTopupConfigResponse:
    """
    创建或更新指定用户的自动充值规则。

    仅当 current_user.is_superuser 为 True 时允许调用。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以查看或修改自动充值配置")

    if payload.target_balance <= payload.min_balance_threshold:
        raise bad_request(
            "target_balance 必须大于 min_balance_threshold",
            details={
                "min_balance_threshold": payload.min_balance_threshold,
                "target_balance": payload.target_balance,
            },
        )

    rule = upsert_auto_topup_rule(
        db,
        user_id=user_id,
        min_balance_threshold=payload.min_balance_threshold,
        target_balance=payload.target_balance,
        is_active=payload.is_active,
    )
    return CreditAutoTopupConfigResponse.model_validate(rule)


@router.delete(
    "/admin/users/{user_id}/auto-topup",
    status_code=status.HTTP_204_NO_CONTENT,
)
def disable_user_auto_topup_config(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> Response:
    """
    禁用指定用户的自动充值规则。

    若规则不存在，则视为幂等成功。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以查看或修改自动充值配置")

    disable_auto_topup_for_user(db, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/admin/auto-topup/batch",
    response_model=CreditAutoTopupBatchResponse,
    status_code=status.HTTP_200_OK,
)
def batch_upsert_auto_topup_config(
    payload: CreditAutoTopupBatchRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditAutoTopupBatchResponse:
    """
    批量为多个用户配置自动充值规则。

    - 管理员在前端多选一批用户后，调用本接口；
    - 对每个 user_id 复用单用户的 upsert 逻辑。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以查看或修改自动充值配置")

    if not payload.user_ids:
        raise bad_request("user_ids 不能为空")

    if payload.target_balance <= payload.min_balance_threshold:
        raise bad_request(
            "target_balance 必须大于 min_balance_threshold",
            details={
                "min_balance_threshold": payload.min_balance_threshold,
                "target_balance": payload.target_balance,
            },
        )

    configs: list[CreditAutoTopupConfigResponse] = []
    for user_id in payload.user_ids:
        rule = upsert_auto_topup_rule(
            db,
            user_id=user_id,
            min_balance_threshold=payload.min_balance_threshold,
            target_balance=payload.target_balance,
            is_active=payload.is_active,
        )
        configs.append(CreditAutoTopupConfigResponse.model_validate(rule))

    return CreditAutoTopupBatchResponse(
        updated_count=len(configs),
        configs=configs,
    )


__all__ = ["router"]
