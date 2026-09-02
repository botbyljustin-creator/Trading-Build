from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import RuleCategory
from app.schemas.citations import SourceCitation

# The extractor never emits USER_DEFINED (that's set only when a human
# types a rule directly — see app/api/routes/rules.py's manual-rule
# endpoint) — so its output is restricted to the three evidence-strength
# levels plus the inferred-gap-filler case.
ExtractionEvidenceType = Literal["EXPLICIT", "IMPLIED", "DISCRETIONARY", "AI_ASSUMPTION"]
QuantifiabilityLiteral = Literal["FULLY_QUANTIFIABLE", "PARTIALLY_QUANTIFIABLE", "DISCRETIONARY"]


class ExtractedRule(BaseModel):
    """One candidate trading rule.

    `evidence_type` replaces a plain "is this an assumption" flag with the
    full classification this system requires: EXPLICIT (the creator
    clearly states it), IMPLIED (strongly implied by repeated examples,
    not stated outright), DISCRETIONARY (the source itself frames this as
    requiring judgment), or AI_ASSUMPTION (the model is inferring a rule to
    fill a gap the source doesn't actually cover). Only AI_ASSUMPTION
    requires explicit human approval before entering a strategy — but all
    four are persisted with their status starting at `EXTRACTED`, never
    silently promoted.
    """

    category: RuleCategory
    natural_language_rule: str = Field(max_length=2000)
    machine_readable_rule: dict | None = Field(
        default=None,
        description=(
            "Best-effort structured hint, e.g. {'type': 'stop_loss', 'method': "
            "'below_swing_low'}. Advisory only — the Strategy Compiler re-derives "
            "the authoritative StrategySpecification field."
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_type: ExtractionEvidenceType = Field(
        description="How directly the source material supports this rule."
    )
    quantifiability: QuantifiabilityLiteral = Field(
        description=(
            "FULLY_QUANTIFIABLE: can drive executable logic as stated. "
            "PARTIALLY_QUANTIFIABLE: some measurable parts, some discretionary language "
            "(e.g. 'strong displacement' needs a numeric definition). "
            "DISCRETIONARY: requires human judgment StrategyForge cannot encode at all."
        )
    )
    sources: list[SourceCitation] = Field(min_length=1)


class RuleExtractionResult(BaseModel):
    rules: list[ExtractedRule] = Field(default_factory=list)
