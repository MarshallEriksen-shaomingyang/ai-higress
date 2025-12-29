"""
积分账户、流水与消费洞察相关路由。

设计目标：
- 普通用户可以查询自己的积分余额与近期流水；
- 管理员可以为指定用户充值/调整积分；
- 仪表盘可通过新增的消费洞察接口展示消费趋势与 Provider 贡献度；
- 具体扣费逻辑在 app.services.credit_service 中实现，路由层只做薄封装。
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import bad_request, forbidden, http_error
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.models import CreditAccount, CreditTransaction, Provider
from app.schemas import (
    CreditAccountResponse,
    CreditAutoTopupBatchRequest,
    CreditAutoTopupBatchResponse,
    CreditAutoTopupConfig,
    CreditAutoTopupConfigResponse,
    CreditConsumptionSummary,
    CreditGrantRequest,
    CreditGrantResponse,
    CreditGrantTokenIssueRequest,
    CreditGrantTokenIssueResponse,
    CreditGrantTokenRedeemRequest,
    CreditProviderUsageItem,
    CreditProviderUsageResponse,
    CreditTopupRequest,
    CreditTransactionResponse,
    CreditUsageTimeseriesPoint,
    CreditUsageTimeseriesResponse,
)
from app.services.credit_service import (
    apply_credit_delta,
    apply_manual_delta,
    disable_auto_topup_for_user,
    get_auto_topup_rule_for_user,
    get_or_create_account_for_user,
    upsert_auto_topup_rule,
)
from app.services.credit_grant_token_service import (
    create_credit_grant_token,
    decode_credit_grant_token,
)

router = APIRouter(
    tags=["credits"],
    prefix="/v1/credits",
    dependencies=[Depends(require_jwt_token)],
)

USAGE_REASONS: tuple[str, ...] = ("usage", "stream_usage", "stream_estimate")


def _resolve_time_range(
    time_range: Literal["today", "7d", "30d", "90d", "all"],
) -> tuple[dt.datetime | None, dt.datetime]:
    now = dt.datetime.now(dt.UTC)

    if time_range == "today":
        return (
            now.replace(hour=0, minute=0, second=0, microsecond=0),
            now,
        )
    if time_range == "7d":
        return now - dt.timedelta(days=7), now
    if time_range == "30d":
        return now - dt.timedelta(days=30), now
    if time_range == "90d":
        return now - dt.timedelta(days=90), now
    if time_range == "all":
        return None, now
    # 默认回退到 30 天
    return now - dt.timedelta(days=30), now


def _compute_prev_window(
    start_at: dt.datetime | None,
    end_at: dt.datetime,
) -> tuple[dt.datetime, dt.datetime] | None:
    if start_at is None:
        return None
    window = end_at - start_at
    if window.total_seconds() <= 0:
        return None
    prev_end = start_at
    prev_start = prev_end - window
    return prev_start, prev_end


def _usage_base_query(
    db: Session,
    *,
    user_id: UUID,
    start_at: dt.datetime | None,
    end_at: dt.datetime | None,
):
    q = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user_id)
        .filter(CreditTransaction.amount < 0)
        .filter(CreditTransaction.reason.in_(USAGE_REASONS))
    )
    if start_at is not None:
        q = q.filter(CreditTransaction.created_at >= start_at)
    if end_at is not None:
        q = q.filter(CreditTransaction.created_at < end_at)
    return q


def _usage_stats(
    db: Session,
    *,
    user_id: UUID,
    start_at: dt.datetime | None,
    end_at: dt.datetime | None,
) -> tuple[int, int]:
    q = _usage_base_query(db, user_id=user_id, start_at=start_at, end_at=end_at)
    row = q.with_entities(
        func.coalesce(func.sum(-CreditTransaction.amount), 0).label("spent"),
        func.coalesce(func.count(CreditTransaction.id), 0).label("count"),
    ).one()
    spent = int(row.spent or 0)
    return spent, int(row.count or 0)


def _window_days(
    db: Session,
    *,
    user_id: UUID,
    start_at: dt.datetime | None,
    end_at: dt.datetime,
) -> int:
    if start_at is not None:
        delta = end_at - start_at
        return max(1, math.ceil(delta.total_seconds() / 86400))

    earliest = (
        _usage_base_query(db, user_id=user_id, start_at=None, end_at=None)
        .with_entities(CreditTransaction.created_at)
        .order_by(CreditTransaction.created_at.asc())
        .limit(1)
        .scalar()
    )
    if earliest is None:
        return 1
    delta = end_at - earliest
    return max(1, math.ceil(delta.total_seconds() / 86400))


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


@router.get("/me/transactions", response_model=list[CreditTransactionResponse])
def list_my_transactions(
    limit: int = Query(50, ge=1, le=100, description="返回的最大记录数"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
    start_date: str | None = Query(None, description="开始日期（ISO 8601格式）"),
    end_date: str | None = Query(None, description="结束日期（ISO 8601格式）"),
    reason: str | None = Query(None, description="流水原因过滤（如：usage、stream_estimate、admin_topup 等）"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> list[CreditTransactionResponse]:
    """
    分页返回当前用户的积分流水记录（按时间倒序）。
    
    支持按日期范围和原因过滤：
    - start_date, end_date: ISO 8601格式的日期范围
    - reason: 流水原因（usage、stream_estimate、admin_topup、adjust 等）
    """
    from datetime import datetime

    # 通过 user_id 维度过滤，避免暴露其他用户数据。
    q = (
        db.query(CreditTransaction)
        .join(CreditAccount, CreditTransaction.account_id == CreditAccount.id)
        .filter(CreditAccount.user_id == UUID(current_user.id))
    )

    # 按日期范围过滤
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            q = q.filter(CreditTransaction.created_at >= start_dt)
        except ValueError:
            raise bad_request(f"无效的 start_date 格式：{start_date}")

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            q = q.filter(CreditTransaction.created_at <= end_dt)
        except ValueError:
            raise bad_request(f"无效的 end_date 格式：{end_date}")

    # 按原因过滤
    if reason:
        q = q.filter(CreditTransaction.reason == reason)

    q = q.order_by(CreditTransaction.created_at.desc()).offset(offset).limit(limit)
    items = q.all()
    return [CreditTransactionResponse.model_validate(item) for item in items]


@router.get(
    "/me/consumption/summary",
    response_model=CreditConsumptionSummary,
    summary="当前用户积分消耗概览（按时间范围聚合）",
)
def get_my_consumption_summary(
    time_range: Literal["today", "7d", "30d", "90d", "all"] = Query(
        "30d",
        description="统计窗口：today/7d/30d/90d/all",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditConsumptionSummary:
    """
    返回当前用户在指定时间范围内的积分消耗合计、交易次数、环比以及余额预测。
    """
    user_id = UUID(current_user.id)
    start_at, end_at = _resolve_time_range(time_range)
    prev_window = _compute_prev_window(start_at, end_at)

    spent, tx_count = _usage_stats(
        db,
        user_id=user_id,
        start_at=start_at,
        end_at=end_at,
    )

    if prev_window is not None:
        spent_prev, _ = _usage_stats(
            db,
            user_id=user_id,
            start_at=prev_window[0],
            end_at=prev_window[1],
        )
    else:
        spent_prev = None

    account = get_or_create_account_for_user(db, user_id)
    balance = int(account.balance)

    window_days = _window_days(
        db,
        user_id=user_id,
        start_at=start_at,
        end_at=end_at,
    )
    avg_daily_spent = spent / window_days if window_days > 0 else 0
    if avg_daily_spent > 0:
        projected_days_left = balance / avg_daily_spent
    else:
        projected_days_left = None

    return CreditConsumptionSummary(
        time_range=time_range,
        start_at=start_at,
        end_at=end_at,
        spent_credits=spent,
        spent_credits_prev=spent_prev,
        transactions=tx_count,
        avg_daily_spent=avg_daily_spent,
        balance=balance,
        projected_days_left=projected_days_left,
    )


@router.get(
    "/me/consumption/providers",
    response_model=CreditProviderUsageResponse,
    summary="按 Provider 聚合的积分消耗列表",
)
def get_my_provider_consumption(
    time_range: Literal["today", "7d", "30d", "90d", "all"] = Query(
        "30d",
        description="统计窗口：today/7d/30d/90d/all",
    ),
    limit: int = Query(
        6,
        ge=1,
        le=50,
        description="返回的 Provider 数量（按消耗降序）",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditProviderUsageResponse:
    """
    返回当前用户在指定时间范围内，各 Provider 的积分消耗排名。
    """
    user_id = UUID(current_user.id)
    start_at, end_at = _resolve_time_range(time_range)
    total_spent, _ = _usage_stats(
        db,
        user_id=user_id,
        start_at=start_at,
        end_at=end_at,
    )

    q = (
        _usage_base_query(db, user_id=user_id, start_at=start_at, end_at=end_at)
        .filter(CreditTransaction.provider_id.isnot(None))
        .with_entities(
            CreditTransaction.provider_id,
            func.sum(-CreditTransaction.amount).label("spent"),
            func.count(CreditTransaction.id).label("tx_count"),
            func.max(CreditTransaction.created_at).label("last_tx"),
        )
        .join(
            Provider,
            Provider.provider_id == CreditTransaction.provider_id,
            isouter=True,
        )
        .add_columns(Provider.name.label("provider_name"))
        .group_by(CreditTransaction.provider_id, Provider.name)
        .order_by(func.sum(-CreditTransaction.amount).desc())
        .limit(limit)
    )

    rows = q.all()

    items: list[CreditProviderUsageItem] = []
    for row in rows:
        spent = int(row.spent or 0)
        percentage = (spent / total_spent) if total_spent > 0 else 0.0
        items.append(
            CreditProviderUsageItem(
                provider_id=row.provider_id,
                provider_name=row.provider_name,
                total_spent=spent,
                transaction_count=int(row.tx_count or 0),
                percentage=percentage,
                last_transaction_at=row.last_tx,
            )
        )

    return CreditProviderUsageResponse(
        time_range=time_range,
        total_spent=total_spent,
        items=items,
    )


@router.get(
    "/me/consumption/timeseries",
    response_model=CreditUsageTimeseriesResponse,
    summary="积分消耗时间序列（按日聚合）",
)
def get_my_consumption_timeseries(
    time_range: Literal["today", "7d", "30d", "90d", "all"] = Query(
        "30d",
        description="统计窗口：today/7d/30d/90d/all",
    ),
    bucket: Literal["day"] = Query(
        "day",
        description="聚合粒度，目前仅支持 day",
    ),
    max_points: int = Query(
        90,
        ge=10,
        le=365,
        description="最多返回的点数量，避免一次性返回过多数据",
    ),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditUsageTimeseriesResponse:
    """
    返回按日期聚合的积分消耗时间序列，用于折线/柱状图。
    """
    if bucket != "day":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 bucket=day",
        )

    user_id = UUID(current_user.id)
    start_at, end_at = _resolve_time_range(time_range)

    bucket_expr = func.date(CreditTransaction.created_at)
    q = (
        _usage_base_query(db, user_id=user_id, start_at=start_at, end_at=end_at)
        .with_entities(
            bucket_expr.label("bucket_start"),
            func.sum(-CreditTransaction.amount).label("spent"),
        )
        .group_by(bucket_expr)
        .order_by(bucket_expr.desc())
        .limit(max_points)
    )

    rows = q.all()
    rows.reverse()
    points: list[CreditUsageTimeseriesPoint] = []
    for row in rows:
        bucket_start = row.bucket_start
        if isinstance(bucket_start, dt.date) and not isinstance(bucket_start, dt.datetime):
            bucket_dt = dt.datetime.combine(
                bucket_start,
                dt.time.min,
                tzinfo=dt.UTC,
            )
        elif isinstance(bucket_start, dt.datetime):
            bucket_dt = bucket_start
        else:
            bucket_dt = dt.datetime.now(dt.UTC)

        points.append(
            CreditUsageTimeseriesPoint(
                window_start=bucket_dt,
                spent_credits=int(row.spent or 0),
            )
        )

    return CreditUsageTimeseriesResponse(
        time_range=time_range,
        bucket=bucket,
        points=points,
    )


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


@router.post(
    "/admin/users/{user_id}/grant",
    response_model=CreditGrantResponse,
    status_code=status.HTTP_200_OK,
)
def admin_grant_user_credits(
    user_id: UUID,
    payload: CreditGrantRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditGrantResponse:
    """
    管理员为指定用户执行“积分入账”（可用于签到/兑换码/活动赠送等场景）。

    - 与 /topup 的区别：支持自定义 reason 与可选 idempotency_key（幂等入账）。
    - 仅当 current_user.is_superuser 为 True 时允许调用。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以调整用户积分")

    try:
        account, tx, applied = apply_credit_delta(
            db,
            user_id=user_id,
            amount=payload.amount,
            reason=payload.reason,
            description=payload.description,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise bad_request(str(exc))

    return CreditGrantResponse(
        applied=applied,
        account=CreditAccountResponse.model_validate(account),
        transaction=CreditTransactionResponse.model_validate(tx) if tx else None,
    )

@router.post(
    "/admin/grant-tokens",
    response_model=CreditGrantTokenIssueResponse,
    status_code=status.HTTP_200_OK,
)
def admin_issue_credit_grant_token(
    payload: CreditGrantTokenIssueRequest,
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditGrantTokenIssueResponse:
    """
    管理员签发“积分入账 token”，用于面向普通用户的受控兑换/活动入账。

    仅当 current_user.is_superuser 为 True 时允许调用。
    """
    if not current_user.is_superuser:
        raise forbidden("只有超级管理员可以签发积分兑换 token")

    try:
        token, _issued_at, expires_at = create_credit_grant_token(
            target_user_id=payload.user_id,
            amount=payload.amount,
            reason=payload.reason,
            description=payload.description,
            idempotency_key=payload.idempotency_key,
            expires_in_seconds=payload.expires_in_seconds,
        )
    except ValueError as exc:
        raise bad_request(str(exc))

    return CreditGrantTokenIssueResponse(token=token, expires_at=expires_at)


@router.post(
    "/me/grant-token",
    response_model=CreditGrantResponse,
    status_code=status.HTTP_200_OK,
)
def redeem_my_credit_grant_token(
    payload: CreditGrantTokenRedeemRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> CreditGrantResponse:
    """
    兑换“积分入账 token”，将 token 中的积分入账到当前用户。

    - token 由管理员或活动系统签发（HS256，基于 SECRET_KEY）；
    - 兑换幂等：同一个 token（本质是同一个 idempotency_key）只会成功入账一次。
    """
    try:
        token_data = decode_credit_grant_token(payload.token)
    except ValueError as exc:
        raise bad_request(str(exc))
    except RuntimeError as exc:
        raise http_error(500, error="internal_error", message=str(exc))

    user_id = UUID(current_user.id)
    if token_data.target_user_id is not None and token_data.target_user_id != user_id:
        raise forbidden("该兑换 token 不属于当前用户")

    try:
        account, tx, applied = apply_credit_delta(
            db,
            user_id=user_id,
            amount=token_data.amount,
            reason=token_data.reason,
            description=token_data.description,
            idempotency_key=token_data.idempotency_key,
        )
    except ValueError as exc:
        raise http_error(409, error="conflict", message=str(exc))

    return CreditGrantResponse(
        applied=applied,
        account=CreditAccountResponse.model_validate(account),
        transaction=CreditTransactionResponse.model_validate(tx) if tx else None,
    )


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
