from __future__ import annotations

from pydantic import BaseModel, Field


class SemanticMatchResult(BaseModel):
    is_match: bool
    reason: str = Field(
        default="",
    )
