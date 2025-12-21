"""
Token 相关的 Schema 定义
用于 JWT token 的 Redis 存储和会话管理
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DeviceInfo(BaseModel):
    """设备信息"""
    user_agent: str | None = Field(None, description="用户代理字符串")
    ip_address: str | None = Field(None, description="IP 地址")


class TokenRecord(BaseModel):
    """Token 记录 - 存储在 Redis 中的 token 信息"""
    token_id: str = Field(..., description="Token 唯一标识符")
    user_id: str = Field(..., description="用户 ID")
    token_type: str = Field(..., description="Token 类型: access 或 refresh")
    jti: str = Field(..., description="JWT ID (JTI)")
    issued_at: datetime = Field(..., description="签发时间")
    expires_at: datetime = Field(..., description="过期时间")
    device_info: DeviceInfo | None = Field(None, description="设备信息")

    # Refresh token 特有字段
    family_id: str | None = Field(None, description="Token 家族 ID（用于追踪轮换链）")
    parent_jti: str | None = Field(None, description="父 token 的 JTI（用于检测重放）")
    revoked: bool = Field(False, description="是否已被撤销")


class TokenBlacklistEntry(BaseModel):
    """Token 黑名单条目"""
    jti: str = Field(..., description="JWT ID")
    user_id: str = Field(..., description="用户 ID")
    revoked_at: datetime = Field(..., description="撤销时间")
    reason: str = Field(..., description="撤销原因")


class UserSession(BaseModel):
    """用户会话信息"""
    session_id: str = Field(..., description="会话 ID")
    refresh_token_jti: str = Field(..., description="Refresh token 的 JTI")
    created_at: datetime = Field(..., description="创建时间")
    last_used_at: datetime = Field(..., description="最后使用时间")
    device_info: DeviceInfo | None = Field(None, description="设备信息")


class SessionResponse(BaseModel):
    """会话响应 - 返回给客户端的会话信息"""
    session_id: str = Field(..., description="会话 ID")
    created_at: datetime = Field(..., description="创建时间")
    last_used_at: datetime = Field(..., description="最后使用时间")
    device_info: DeviceInfo | None = Field(None, description="设备信息")
    is_current: bool = Field(..., description="是否为当前会话")


class TokenPair(BaseModel):
    """Token 对 - 包含 access token 和 refresh token"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    access_token_jti: str = Field(..., description="访问令牌的 JTI")
    refresh_token_jti: str = Field(..., description="刷新令牌的 JTI")
    family_id: str = Field(..., description="Token 家族 ID")


__all__ = [
    "DeviceInfo",
    "SessionResponse",
    "TokenBlacklistEntry",
    "TokenPair",
    "TokenRecord",
    "UserSession",
]
