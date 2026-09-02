from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import RuleCategory
from app.schemas.citations import SourceCitation


class ExtractedRule(BaseModel):
    """One candidate trading rule. `is_assumption=True` means the model is
    inferring a rule rather than quoting/closely paraphrasing something the
    creator explicitly stated — such rules are persisted with status
    `AI_ASSUMPTION` and are structurally barred from a compiled strategy
    until a human explicitly promotes them (see `COMPILABLE_RULE_STATUSES`).
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
    is_assumption: bool = Field(
        default=False,
        description="True if this rule is inferred rather than explicitly stated by the creator.",
    )
    sources: list[SourceCitation] = Field(min_length=1)


class RuleExtractionResult(BaseModel):
    rules: list[ExtractedRule] = Field(default_factory=list)
