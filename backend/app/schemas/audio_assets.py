from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


AudioAssetVisibility = Literal["private", "public"]


class AudioAssetItem(BaseModel):
    audio_id: UUID
    owner_id: UUID
    owner_username: str
    owner_display_name: str | None = None
    conversation_id: UUID | None = None

    object_key: str
    url: HttpUrl
    content_type: str
    size_bytes: int
    format: Literal["wav", "mp3"]
    filename: str | None = None
    display_name: str | None = None
    visibility: AudioAssetVisibility

    created_at: datetime
    updated_at: datetime

    model_config = {"extra": "forbid"}


class AudioAssetListResponse(BaseModel):
    items: list[AudioAssetItem] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class AudioAssetVisibilityUpdateRequest(BaseModel):
    visibility: AudioAssetVisibility

    model_config = {"extra": "forbid"}


__all__ = [
    "AudioAssetItem",
    "AudioAssetListResponse",
    "AudioAssetVisibility",
    "AudioAssetVisibilityUpdateRequest",
]

