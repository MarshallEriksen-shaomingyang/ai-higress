from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreateRequest(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
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
    def ensure_any_field(self) -> "UserUpdateRequest":
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


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    display_name: str | None = None
    avatar: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "UserCreateRequest",
    "UserResponse",
    "UserStatusUpdateRequest",
    "UserUpdateRequest",
]
