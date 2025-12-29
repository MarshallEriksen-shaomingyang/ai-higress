from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import User
from app.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]


RISK_LEVEL_LOW = "low"
RISK_LEVEL_MEDIUM = "medium"
RISK_LEVEL_HIGH = "high"

_RISK_LEVELS: tuple[str, ...] = (RISK_LEVEL_LOW, RISK_LEVEL_MEDIUM, RISK_LEVEL_HIGH)

# “稳定异常”窗口：按小时桶聚合近 24 小时（可用于“管理员不实时盯盘”的场景）。
RISK_WINDOW_HOURS = 24
RISK_BUCKET_TTL_SECONDS = 14 * 24 * 60 * 60

# 风险评估节流：同一用户在短时间内只评估一次，避免每个请求都做 ZUNIONSTORE。
RISK_EVAL_COOLDOWN_SECONDS = 10 * 60
RISK_EVAL_LOCK_TTL_SECONDS = 60


@dataclass(frozen=True)
class UserRiskStatus:
    score: int
    level: str
    remark: str | None
    unique_ips: int = 0
    total_requests: int = 0


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _hour_bucket(now: dt.datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.UTC)
    else:
        now = now.astimezone(dt.UTC)
    return now.strftime("%Y%m%d%H")


def _recent_hour_buckets(*, hours: int, now: dt.datetime) -> list[str]:
    buckets: list[str] = []
    for offset in range(max(1, int(hours))):
        buckets.append(_hour_bucket(now - dt.timedelta(hours=offset)))
    return buckets


def _ip_zset_key(user_id: str, hour_bucket: str) -> str:
    return f"risk:user:{user_id}:ips:{hour_bucket}"


def _req_counter_key(user_id: str, hour_bucket: str) -> str:
    return f"risk:user:{user_id}:req:{hour_bucket}"


def _eval_lock_key(user_id: str) -> str:
    return f"risk:user:{user_id}:eval_lock"


def _last_eval_key(user_id: str) -> str:
    return f"risk:user:{user_id}:last_eval_at"


def extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


def _hash_ip(ip: str) -> str:
    secret = settings.secret_key.encode("utf-8")
    msg = ip.encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


async def record_user_ip_signal(
    redis: Redis,
    *,
    user_id: str,
    request: Request,
) -> None:
    """
    在 Redis 中记录“用户 -> IP”小时桶计数（只存 HMAC hash，不存明文 IP）。

    说明：
    - 原始过程数据仅用于风险计算，不落库；
    - 所有 key 会设置 TTL，避免无限增长。
    """
    if not user_id or redis is object:
        return

    client_ip = extract_client_ip(request)
    if not client_ip or client_ip == "unknown":
        return

    now = _utc_now()
    bucket = _hour_bucket(now)
    ip_hash = _hash_ip(client_ip)
    zset_key = _ip_zset_key(user_id, bucket)
    counter_key = _req_counter_key(user_id, bucket)

    try:
        await redis.zincrby(zset_key, 1, ip_hash)
        await redis.expire(zset_key, RISK_BUCKET_TTL_SECONDS)
        await redis.incr(counter_key)
        await redis.expire(counter_key, RISK_BUCKET_TTL_SECONDS)
    except Exception:  # pragma: no cover - best effort
        logger.debug("user_risk: failed to record ip signal (user_id=%s)", user_id, exc_info=True)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _clamp_score(score: int) -> int:
    return max(0, min(100, int(score)))


def _level_for_score(score: int) -> str:
    if score >= 80:
        return RISK_LEVEL_HIGH
    if score >= 50:
        return RISK_LEVEL_MEDIUM
    return RISK_LEVEL_LOW


def _compute_risk_status(
    *,
    unique_ips: int,
    total_requests: int,
    top_ip_counts: list[int],
) -> UserRiskStatus:
    """
    风险评分（0..100）：
    - 核心规则：多 IP 且 top3 频率几乎相同（疑似脚本/共享）。
    - 辅助规则：IP 离散度过高 / 总请求量过高。
    """
    score = 0
    reasons: list[str] = []

    if unique_ips >= 3 and total_requests >= 300 and len(top_ip_counts) >= 3:
        top3 = top_ip_counts[:3]
        top3_max = max(top3)
        top3_min = max(1, min(top3))
        ratio = top3_max / top3_min
        top1_share = top3_max / max(1, total_requests)
        if ratio <= 1.2 and top1_share <= 0.6:
            score += 80
            reasons.append("多 IP 且频率均匀（疑似脚本/共享）")

    if unique_ips >= 5 and total_requests >= 500:
        score += 15
        reasons.append("IP 离散度偏高")
    if unique_ips >= 10:
        score += 25
        reasons.append("IP 离散度过高")

    if total_requests >= 10000:
        score += 10
        reasons.append("请求量异常偏高")

    score = _clamp_score(score)
    level = _level_for_score(score)
    remark = "；".join(reasons) if reasons else None
    return UserRiskStatus(
        score=score,
        level=level,
        remark=remark,
        unique_ips=int(unique_ips),
        total_requests=int(total_requests),
    )


async def evaluate_user_risk_window(
    redis: Redis,
    *,
    user_id: str,
    now: dt.datetime | None = None,
    window_hours: int = RISK_WINDOW_HOURS,
) -> UserRiskStatus:
    if not user_id or redis is object:
        return UserRiskStatus(score=0, level=RISK_LEVEL_LOW, remark=None)

    at = now or _utc_now()
    buckets = _recent_hour_buckets(hours=window_hours, now=at)
    zset_keys = [_ip_zset_key(user_id, b) for b in buckets]
    req_keys = [_req_counter_key(user_id, b) for b in buckets]

    total_requests = 0
    try:
        req_values = await redis.mget(req_keys)
        total_requests = sum(_safe_int(v) for v in (req_values or []))
    except Exception:  # pragma: no cover - best effort
        logger.debug("user_risk: failed to read request counters (user_id=%s)", user_id, exc_info=True)

    # 汇总窗口内的 IP 分布：ZUNIONSTORE + ZCARD + ZREVRANGE(top3)。
    temp_key = f"risk:user:{user_id}:tmp:{secrets.token_hex(8)}"
    unique_ips = 0
    top_ip_counts: list[int] = []

    try:
        # 兼容性：部分测试环境可能没有这些 key，对空列表做兜底。
        if zset_keys:
            await redis.zunionstore(temp_key, zset_keys, aggregate="SUM")
            await redis.expire(temp_key, 60)
            unique_ips = _safe_int(await redis.zcard(temp_key))
            top3 = await redis.zrevrange(temp_key, 0, 2, withscores=True)
            top_ip_counts = [int(score) for _, score in (top3 or [])]
    except Exception:  # pragma: no cover - best effort
        logger.debug("user_risk: failed to union ip buckets (user_id=%s)", user_id, exc_info=True)
    finally:
        try:
            if redis is not object:
                await redis.delete(temp_key)
        except Exception:
            pass

    return _compute_risk_status(
        unique_ips=unique_ips,
        total_requests=total_requests,
        top_ip_counts=top_ip_counts,
    )


async def refresh_user_risk_status(
    redis: Redis,
    *,
    db: Session,
    user_id: UUID,
    force: bool = False,
) -> None:
    """
    评估并将风险结论写入数据库（只在发生变化时更新）。

    注意：该函数应视为 best-effort，不应影响主请求流程。
    """
    if redis is object:
        return

    uid = str(user_id)
    now = _utc_now()

    try:
        locked = await redis.set(
            _eval_lock_key(uid),
            "1",
            nx=True,
            ex=RISK_EVAL_LOCK_TTL_SECONDS,
        )
        if not locked:
            return

        if not force:
            last_raw = await redis.get(_last_eval_key(uid))
            last_ts = _safe_int(last_raw)
            if last_ts > 0 and int(now.timestamp()) - last_ts < RISK_EVAL_COOLDOWN_SECONDS:
                return

        status = await evaluate_user_risk_window(redis, user_id=uid, now=now)
        try:
            await redis.set(_last_eval_key(uid), str(int(now.timestamp())), ex=2 * 24 * 60 * 60)
        except Exception:
            pass

        user = db.get(User, user_id)
        if user is None:
            return

        next_level = status.level if status.level in _RISK_LEVELS else RISK_LEVEL_LOW
        next_score = int(status.score)
        next_remark = status.remark

        changed = (
            getattr(user, "risk_level", RISK_LEVEL_LOW) != next_level
            or _safe_int(getattr(user, "risk_score", 0)) != next_score
            or (getattr(user, "risk_remark", None) or None) != (next_remark or None)
        )
        if not changed:
            return

        user.risk_level = next_level
        user.risk_score = next_score
        user.risk_remark = next_remark
        user.risk_updated_at = now
        db.add(user)
        db.commit()
    except Exception:  # pragma: no cover - best effort
        try:
            db.rollback()
        except Exception:
            pass
        logger.debug("user_risk: failed to refresh status (user_id=%s)", user_id, exc_info=True)


__all__ = [
    "RISK_LEVEL_HIGH",
    "RISK_LEVEL_LOW",
    "RISK_LEVEL_MEDIUM",
    "UserRiskStatus",
    "evaluate_user_risk_window",
    "extract_client_ip",
    "record_user_ip_signal",
    "refresh_user_risk_status",
]
