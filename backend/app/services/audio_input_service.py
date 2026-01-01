from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.services.audio_storage_service import (
    AudioStorageNotConfigured,
    assert_audio_object_key_for_user,
    encode_audio_base64,
    load_audio_bytes,
)
from app.models import AudioAsset

MAX_INPUT_AUDIO_BYTES = 10 * 1024 * 1024


class InputAudioMaterializeError(Exception):
    """
    在“发送上游请求前”物化 input_audio 失败的错误。

    该错误用于流式候选重试层（candidate_retry）：
    - status_code: 用于在 SSE 错误帧里展示
    - retryable: 是否应该切换到下一个 provider 重试
    - penalize: 是否应惩罚 provider（本类错误通常是请求/存储问题，不应惩罚）
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        penalize: bool = False,
        error_category: str = "invalid_input_audio",
    ) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.retryable = bool(retryable)
        self.penalize = bool(penalize)
        self.error_category = str(error_category or "invalid_input_audio")


def _infer_audio_format_from_object_key(object_key: str) -> str:
    key = str(object_key or "").strip().lower()
    if key.endswith(".mp3"):
        return "mp3"
    return "wav"


async def materialize_input_audio_in_payload(
    payload: dict[str, Any],
    *,
    user_id: str,
    db: Session | None = None,
) -> dict[str, Any]:
    """
    将 OpenAI chat.completions 风格的 payload 中的 input_audio 引用（object_key）替换为 base64 data。

    约定：
    - 仅处理 messages[].content 为 list 的情况；
    - 仅处理 part.type == "input_audio" 的 part；
    - part.input_audio 允许形如：
      - {"object_key": "...", "format": "wav"|"mp3"}  （物化为 {"data": "...", "format": ...}）
      - {"data": "...", "format": ...}              （已物化，跳过）
    """
    if not isinstance(payload, dict):
        return payload

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return payload

    cache: dict[str, tuple[str, str]] = {}

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list) or not content:
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if str(part.get("type") or "") != "input_audio":
                continue

            input_audio = part.get("input_audio")
            if not isinstance(input_audio, dict):
                raise ValueError("input_audio 结构不合法")

            if isinstance(input_audio.get("data"), str) and input_audio.get("data"):
                continue

            object_key = input_audio.get("object_key")
            audio_id = input_audio.get("audio_id")

            if audio_id is not None and (not isinstance(object_key, str) or not object_key.strip()):
                if db is None:
                    raise ValueError("input_audio.audio_id 需要服务端 DB 支持")
                try:
                    audio_uuid = UUID(str(audio_id))
                except Exception as exc:
                    raise ValueError("input_audio.audio_id 不合法") from exc
                if not audio_uuid:
                    raise ValueError("input_audio.audio_id 不合法")
                row = (
                    db.execute(
                        select(AudioAsset.object_key, AudioAsset.owner_id, AudioAsset.visibility)
                        .where(AudioAsset.id == audio_uuid)
                        .limit(1)
                    )
                    .first()
                )
                if row is None:
                    raise FileNotFoundError("audio asset not found")
                object_key = str(row[0] or "").strip()
                input_audio["object_key"] = object_key

            if not isinstance(object_key, str) or not object_key.strip():
                raise ValueError("input_audio.object_key 不能为空")
            object_key = object_key.strip()

            # 访问控制：
            # - 自己的命名空间：直接允许
            # - 否则：需要在 audio_assets 中存在 public 或 owner 匹配记录
            allowed = False
            try:
                assert_audio_object_key_for_user(object_key, user_id=str(user_id))
                allowed = True
            except Exception:
                allowed = False

            if not allowed and db is not None:
                try:
                    user_uuid = UUID(str(user_id))
                except Exception:
                    user_uuid = None
                stmt = select(AudioAsset.id).where(AudioAsset.object_key == object_key)
                if user_uuid is not None:
                    stmt = stmt.where((AudioAsset.visibility == "public") | (AudioAsset.owner_id == user_uuid))
                else:
                    stmt = stmt.where(AudioAsset.visibility == "public")
                asset_row = db.execute(stmt.limit(1)).scalars().first()
                allowed = asset_row is not None

            if not allowed:
                raise ValueError("invalid audio object key for user")

            if object_key in cache:
                data_b64, fmt = cache[object_key]
            else:
                body, _content_type = await load_audio_bytes(object_key)
                if not body:
                    raise ValueError("input_audio 为空")
                if len(body) > MAX_INPUT_AUDIO_BYTES:
                    raise ValueError("input_audio 过大，最大支持 10MB")
                data_b64 = encode_audio_base64(body)
                fmt = str(input_audio.get("format") or "").strip().lower()
                if fmt not in {"wav", "mp3"}:
                    fmt = _infer_audio_format_from_object_key(object_key)
                cache[object_key] = (data_b64, fmt)

            part["input_audio"] = {"data": data_b64, "format": fmt}
            part.pop("audio", None)

    return payload


__all__ = [
    "AudioStorageNotConfigured",
    "InputAudioMaterializeError",
    "MAX_INPUT_AUDIO_BYTES",
    "materialize_input_audio_in_payload",
]
