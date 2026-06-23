from __future__ import annotations

from pydantic import BaseModel, Field


class SemanticMatchResult(BaseModel):
    is_match: bool
    reason: str = Field(
        default="",
    )


class FuzzyMatchResult(BaseModel):
    is_match: bool
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    reason: str = Field(
        default="",
    )
