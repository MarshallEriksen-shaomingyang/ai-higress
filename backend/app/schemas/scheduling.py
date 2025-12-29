from pydantic import BaseModel, Field


class SchedulingStrategy(BaseModel):
    """
    Configuration for the routing scheduler scoring algorithm.
    """

    name: str = Field(..., description="Strategy name")
    description: str = Field(
        default="Default routing strategy", description="Human-readable description"
    )
    alpha: float = Field(
        default=0.3, description="Latency weight coefficient", ge=0.0
    )
    beta: float = Field(
        default=0.3, description="Error-rate weight coefficient", ge=0.0
    )
    gamma: float = Field(
        default=0.2, description="Cost weight coefficient", ge=0.0
    )
    delta: float = Field(
        default=0.2, description="Quota penalty coefficient", ge=0.0
    )
    min_score: float = Field(
        default=0.1, description="Minimum valid score threshold", ge=0.0
    )


__all__ = ["SchedulingStrategy"]
