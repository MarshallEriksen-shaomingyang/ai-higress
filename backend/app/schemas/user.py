from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .credit import CreditAutoTopupConfigResponse


class UserCreateRequest(BaseModel):
    username: str | None = Field(
        None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)
    avatar: str | None = Field(default=None, max_length=512)


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)
    avatar: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def ensure_any_field(self) -> UserUpdateRequest:
        if (
            self.email is None
            and self.password is None
            and self.display_name is None
            and self.avatar is None
        ):
            raise ValueError("至少需要提供一个可更新字段")
        return self


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserPermissionFlag(BaseModel):
    """前端可见的权限能力标记，用列表封装布尔值。"""

    key: str = Field(
        ...,
        description="权限能力键，例如 can_create_private_provider",
    )
    value: bool = Field(
        ...,
        description="该能力是否启用",
    )


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    display_name: str | None = None
    avatar: str | None = None
    is_active: bool
    is_superuser: bool
    # 是否需要人工审核后才能启用（用于注册接口返回提示）
    requires_manual_activation: bool = False
    # 当前用户拥有的角色编码列表（例如 ["default_user", "system_admin"]）
    role_codes: list[str] = Field(default_factory=list)
    # 能力标记列表，用于前端控制界面权限（后端仍做强校验）
    permission_flags: list[UserPermissionFlag] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(UserResponse):
    """
    管理员视角的用户信息。

    在 UserResponse 的基础上补充后台管理页面需要的扩展字段。
    """

    credit_auto_topup: CreditAutoTopupConfigResponse | None = Field(
        default=None,
        description="该用户的自动充值配置；未配置时为 null",
    )

    risk_score: int = Field(
        default=0,
        description="风险评分（0-100）；用于管理员列表排序/筛选",
        ge=0,
        le=100,
    )
    risk_level: str = Field(
        default="low",
        description="风险等级：low/medium/high；用于管理员列表标注与筛选",
    )
    risk_remark: str | None = Field(
        default=None,
        description="风险说明（管理员可见），例如“多 IP 且频率均匀（疑似脚本/共享）”",
    )
    risk_updated_at: datetime | None = Field(
        default=None,
        description="风险状态最后更新时间（UTC）",
    )


class UserLookupResponse(BaseModel):
    """用于前端搜索/选择用户时的精简信息。"""

    id: UUID
    username: str
    email: EmailStr
    display_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "AdminUserResponse",
    "UserCreateRequest",
    "UserLookupResponse",
    "UserPermissionFlag",
    "UserResponse",
    "UserStatusUpdateRequest",
    "UserUpdateRequest",
]
