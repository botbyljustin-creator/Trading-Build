"""Source-citation primitives shared by every extraction schema.

Every AI-generated claim in this system carries one of these. There is no
"trust me" field — a `SourceCitation` always has a concrete video + time
range + verbatim excerpt so a human can go verify it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    video_id: str = Field(description="Internal video UUID (string) this excerpt came from.")
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    excerpt: str = Field(
        min_length=1,
        max_length=2000,
        description="Verbatim (not paraphrased) transcript excerpt supporting the claim.",
    )
