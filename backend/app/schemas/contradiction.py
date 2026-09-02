from __future__ import annotations

from pydantic import BaseModel, Field


class ContradictionCandidate(BaseModel):
    """A potential conflict between two already-extracted rules, identified
    by the `rule_id` values given in the prompt's rule listing — the model
    never needs to reproduce rule text or sources, which keeps matching
    back to `Rule` rows exact rather than fuzzy."""

    rule_a_id: str
    rule_b_id: str
    explanation: str = Field(description="Why these two rules conflict, in plain language.")


class ContradictionDetectionResult(BaseModel):
    contradictions: list[ContradictionCandidate] = Field(default_factory=list)
