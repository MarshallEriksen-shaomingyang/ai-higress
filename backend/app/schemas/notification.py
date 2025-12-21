from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

NotificationLevel = Literal["info", "success", "warning", "error"]
NotificationTargetType = Literal["all", "users", "roles"]


class NotificationCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="通知标题")
    content: str = Field(..., min_length=1, max_length=4000, description="通知正文")
    level: NotificationLevel = Field(
        "info",
        description="通知等级：info/success/warning/error",
    )
    target_type: NotificationTargetType = Field(
        "all",
        description="受众类型：all=全部用户，users=指定用户，roles=指定角色",
    )
    target_user_ids: list[UUID] = Field(
        default_factory=list,
        description="当 target_type=users 时的目标用户 ID 列表",
    )
    target_role_codes: list[str] = Field(
        default_factory=list,
        description="当 target_type=roles 时的目标角色 code 列表",
    )
    link_url: str | None = Field(
        default=None,
        max_length=512,
        description="点击通知时可跳转的链接",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="通知过期时间，过期后对用户不可见",
    )

    @model_validator(mode="after")
    def validate_targets(self) -> NotificationCreateRequest:
        if self.target_type == "users" and not self.target_user_ids:
            raise ValueError("target_user_ids 不能为空")
        if self.target_type == "roles" and not self.target_role_codes:
            raise ValueError("target_role_codes 不能为空")
        if self.target_type == "all":
            self.target_user_ids = []
            self.target_role_codes = []
        return self


class NotificationResponse(BaseModel):
    id: UUID
    title: str
    content: str
    level: NotificationLevel
    target_type: NotificationTargetType
    target_user_ids: list[UUID]
    target_role_codes: list[str]
    link_url: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    is_read: bool = False
    read_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationAdminResponse(BaseModel):
    id: UUID
    title: str
    content: str
    level: NotificationLevel
    target_type: NotificationTargetType
    target_user_ids: list[UUID]
    target_role_codes: list[str]
    link_url: str | None = None
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationMarkReadRequest(BaseModel):
    notification_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="要标记为已读的通知 ID 列表",
    )


class NotificationMarkReadResponse(BaseModel):
    updated_count: int = Field(..., ge=0, description="成功标记为已读的数量")


class UnreadCountResponse(BaseModel):
    unread_count: int = Field(..., ge=0)


__all__ = [
    "NotificationAdminResponse",
    "NotificationCreateRequest",
    "NotificationLevel",
    "NotificationMarkReadRequest",
    "NotificationMarkReadResponse",
    "NotificationResponse",
    "NotificationTargetType",
    "UnreadCountResponse",
]
