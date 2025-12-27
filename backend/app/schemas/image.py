from typing import Any, Optional, Literal

from pydantic import BaseModel, Field


class ImageGenerationRequest(BaseModel):
    """
    Request body for image generation, compatible with OpenAI API.
    """
    prompt: str = Field(..., description="A text description of the desired image(s).")
    model: str = Field(..., description="The model to use for image generation.")
    n: int = Field(default=1, description="The number of images to generate. Must be between 1 and 10.", ge=1, le=10)
    quality: Optional[Literal["standard", "hd", "low", "medium", "high", "auto"]] = Field(
        default="auto",
        description="The quality of the image that will be generated (OpenAI-compatible).",
    )
    response_format: Optional[Literal["url", "b64_json"]] = Field(
        default="url",
        description="The format in which the generated images are returned.",
    )
    size: Optional[str] = Field(default="1024x1024", description="The size of the generated images (e.g. 1024x1024).")
    style: Optional[Literal["vivid", "natural"]] = Field(default="vivid", description="The style of the generated images.")
    user: Optional[str] = Field(None, description="A unique identifier representing your end-user.")

    # Newer OpenAI image models (GPT image models) additional options
    background: Optional[Literal["transparent", "opaque", "auto"]] = Field(
        default=None,
        description="Background transparency control (GPT image models).",
    )
    moderation: Optional[Literal["low", "auto"]] = Field(
        default=None,
        description="Content moderation level (GPT image models).",
    )
    output_format: Optional[Literal["png", "jpeg", "webp"]] = Field(
        default=None,
        description="Output image format (GPT image models).",
    )
    output_compression: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Output compression level (0-100) for jpeg/webp (GPT image models).",
    )
    stream: Optional[bool] = Field(
        default=None,
        description="Whether to stream partial images (GPT image models).",
    )
    partial_images: Optional[int] = Field(
        default=None,
        ge=0,
        le=3,
        description="Number of partial images to generate for streaming responses (GPT image models).",
    )

    extra_body: dict[str, Any] | None = Field(
        default=None,
        description=(
            "网关保留扩展字段：用于透传特定上游厂商的高级参数。"
            "约定结构：{ \"openai\": {...}, \"google\": {...} }。"
            "网关会在选中对应 lane 时将其合并到上游请求体中。"
        ),
    )


class ImageObject(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageUsage(BaseModel):
    """
    Token usage information for image generation (for some OpenAI image models).
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    input_tokens_details: dict[str, Any] | None = None
    output_tokens_details: dict[str, Any] | None = None


class ImageGenerationResponse(BaseModel):
    created: int = Field(..., description="The Unix timestamp (in seconds) of when the request was created.")
    data: list[ImageObject] = Field(..., description="List of generated images.")
    background: Optional[Literal["transparent", "opaque"]] = Field(default=None)
    output_format: Optional[Literal["png", "jpeg", "webp"]] = Field(default=None)
    quality: Optional[Literal["low", "medium", "high"]] = Field(default=None)
    size: Optional[str] = Field(default=None)
    usage: ImageUsage | None = Field(default=None)
