from __future__ import annotations

from typing import Literal

from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ConversationAudioUploadResponse(BaseModel):
    """
    会话内“用户语音上传”响应体。

    说明：
    - object_key 用于后续发送消息时引用（input_audio.object_key）；
    - url 为网关签名短链，可用于浏览器播放/回放（/media/audio/...）。
    """

    audio_id: UUID = Field(..., description="音频资产 ID（用于后续复用/分享/引用）")
    object_key: str = Field(..., description="对象存储 key（网关内部引用）")
    url: HttpUrl = Field(..., description="网关签名短链，可用于播放/下载")
    content_type: str = Field(..., description="音频 MIME 类型（如 audio/wav、audio/mpeg）")
    size_bytes: int = Field(..., ge=1, description="音频字节大小")
    format: Literal["wav", "mp3"] = Field(..., description="音频格式（从 content_type/文件名推断）")

    model_config = {"extra": "forbid"}


__all__ = ["ConversationAudioUploadResponse"]
