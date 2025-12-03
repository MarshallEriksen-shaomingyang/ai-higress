from pydantic import BaseModel, Field


class Session(BaseModel):
    """
    Conversation-level stickiness information.
    """

    conversation_id: str = Field(..., description="Conversation id / thread id")
    logical_model: str = Field(..., description="Logical model id")
    provider_id: str = Field(..., description="Bound provider id")
    model_id: str = Field(..., description="Chosen physical model id")
    created_at: float = Field(..., description="Creation timestamp (epoch seconds)")
    last_accessed: float = Field(
        ..., description="Last access timestamp (epoch seconds)"
    )
    message_count: int = Field(
        default=0, description="Total messages in this conversation", ge=0
    )


__all__ = ["Session"]

