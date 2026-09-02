from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.citations import SourceCitation


class ExtractedConcept(BaseModel):
    """One trading concept the model found actually present in the source
    material. The Knowledge Builder must not emit a concept it cannot back
    with at least one `SourceCitation`."""

    name: str = Field(max_length=255)
    description: str = Field(
        description="What this concept means, in this creator's own terms, based only on the source."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[SourceCitation] = Field(min_length=1)
    related_concepts: list[str] = Field(
        default_factory=list, description="Names of other concepts this one relates to."
    )
    conflicting_with: list[str] = Field(
        default_factory=list,
        description="Names of other concepts whose sources appear to define this concept differently.",
    )


class ConceptExtractionResult(BaseModel):
    concepts: list[ExtractedConcept] = Field(default_factory=list)
