"""
用户会话管理路由
提供查看和管理用户活跃会话的功能
"""


from fastapi import APIRouter, Depends, HTTPException, status

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = object  # type: ignore[misc,assignment]

from app.deps import get_redis
from app.jwt_auth import AuthenticatedUser, require_jwt_token
from app.schemas.token import SessionResponse
from app.services.token_redis_service import TokenRedisService

router = APIRouter(tags=["sessions"], prefix="/v1/sessions")


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    redis: Redis = Depends(get_redis),
) -> list[SessionResponse]:
    """
    获取当前用户所有活跃会话
    
    Args:
        current_user: 当前认证用户
        redis: Redis 连接
        
    Returns:
        用户会话列表
    """
    token_service = TokenRedisService(redis)
    sessions = await token_service.get_user_sessions(current_user.id)

    # 转换为响应格式
    # 注意：这里无法确定哪个是当前会话，因为我们没有当前 refresh token 的 JTI
    # 可以通过比较设备信息来推测，但不够准确
    response = []
    for session in sessions:
        response.append(
            SessionResponse(
                session_id=session.session_id,
                created_at=session.created_at,
                last_used_at=session.last_used_at,
                device_info=session.device_info,
                is_current=False,  # 暂时无法准确判断
            )
        )

    return response


@router.delete("/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(require_jwt_token),
    redis: Redis = Depends(get_redis),
) -> dict:
    """
    撤销指定会话
    
    Args:
        session_id: 会话 ID（即 refresh token 的 token_id）
        current_user: 当前认证用户
        redis: Redis 连接
        
    Returns:
        撤销结果
    """
    token_service = TokenRedisService(redis)

    # 获取用户所有会话
    sessions = await token_service.get_user_sessions(current_user.id)

    # 查找目标会话
    target_session = None
    for session in sessions:
        if session.session_id == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 撤销该会话的 refresh token
    success = await token_service.revoke_token(
        target_session.refresh_token_jti,
        reason="session_revoked_by_user"
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话撤销失败"
        )

    return {"message": "会话已成功撤销"}


__all__ = ["router"]
