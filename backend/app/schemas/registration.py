from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.registration_window import RegistrationWindowStatus


class RegistrationWindowCreateRequest(BaseModel):
    start_time: datetime = Field(..., description="注册开放的开始时间（必须包含时区）")
    end_time: datetime = Field(..., description="注册开放的结束时间（必须包含时区）")
    max_registrations: int = Field(..., gt=0, description="本轮开放的注册名额上限")

    @field_validator("start_time", "end_time")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("时间字段必须包含时区信息")
        return value

    @model_validator(mode="after")
    def _check_range(self) -> RegistrationWindowCreateRequest:
        if self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class RegistrationWindowResponse(BaseModel):
    id: UUID
    start_time: datetime
    end_time: datetime
    max_registrations: int
    registered_count: int
    auto_activate: bool
    status: RegistrationWindowStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(use_enum_values=True, from_attributes=True)


__all__ = [
    "RegistrationWindowCreateRequest",
    "RegistrationWindowResponse",
    "RegistrationWindowStatus",
]
