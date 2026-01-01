from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SpeechRequest(BaseModel):
    """
    OpenAI-compatible TTS request body.

    说明：
    - 本网关为聚合网关，model 为“逻辑模型 id”，不做固定枚举；
    - voice 保持 OpenAI 常用 voice 形态，便于前端统一；对 Gemini 等上游会做映射。
    """

    model: str = Field(..., min_length=1, description="逻辑模型 ID（将由网关选路到具体上游模型）")
    input: str = Field(..., min_length=1, max_length=4096, description="要生成语音的文本（最大 4096 字符）")
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = Field(
        default="alloy",
        description="语音选项（OpenAI 风格）",
    )
    response_format: Literal["mp3", "opus", "aac", "wav", "pcm", "ogg", "flac", "aiff"] = Field(
        default="mp3",
        description="输出格式（取决于上游能力；网关不做转码）",
    )
    speed: float = Field(1.0, ge=0.25, le=4.0, description="语速（0.25-4.0）")
    instructions: str | None = Field(
        default=None,
        description="可选：语气/情感等指令（部分上游/模型支持）",
    )
    input_type: Literal["text", "ssml"] = Field(
        default="text",
        description="输入类型：text（默认）或 ssml（XML 字符串；是否支持取决于上游）",
    )
    locale: str | None = Field(
        default=None,
        description="可选：语言/地区（如 zh-CN、en-US；是否生效取决于上游/模型）",
    )
    pitch: float | None = Field(
        default=None,
        description="可选：音高（语义值域取决于上游/模型；网关不做统一归一化）",
    )
    volume: float | None = Field(
        default=None,
        description="可选：音量（语义值域取决于上游/模型；网关不做统一归一化）",
    )
    reference_audio_url: HttpUrl | None = Field(
        default=None,
        description="可选：参考音频 URL（部分上游 TTS/克隆音色能力需要；网关用于选路约束）",
    )


class MessageSpeechRequest(BaseModel):
    """
    会话内朗读请求：从消息内容获取文本，再按 model/voice/speed 生成音频。
    """

    model: str | None = Field(
        default=None,
        description="逻辑模型 ID（为空则跟随会话默认）",
    )
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = Field(
        default="alloy",
        description="语音选项（OpenAI 风格）",
    )
    response_format: Literal["mp3", "opus", "aac", "wav", "pcm", "ogg", "flac", "aiff"] = Field(
        default="mp3",
        description="输出格式",
    )
    speed: float = Field(1.0, ge=0.25, le=4.0, description="语速（0.25-4.0）")


__all__ = ["MessageSpeechRequest", "SpeechRequest"]
