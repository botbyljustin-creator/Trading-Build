"""Contradiction Analyst agent (ARCHITECTURE.md §5.4)."""

from __future__ import annotations

from app.ai.base import LLMProvider
from app.ai.prompts.agents import CONTRADICTION_ANALYST_SYSTEM_PROMPT
from app.ai.rendering import RuleSummary, render_rule_summaries
from app.schemas.contradiction import ContradictionDetectionResult

INSTRUCTION = (
    "Given the following already-extracted rules, identify pairs that "
    "directly contradict each other when applied to the same situation. "
    "Reference each rule only by its rule_id shown in its header."
)


def detect_contradictions(
    provider: LLMProvider, rules: list[RuleSummary]
) -> ContradictionDetectionResult:
    if len(rules) < 2:
        return ContradictionDetectionResult(contradictions=[])
    return provider.generate_structured(
        system_prompt=CONTRADICTION_ANALYST_SYSTEM_PROMPT,
        source_content=render_rule_summaries(rules),
        instruction=INSTRUCTION,
        response_model=ContradictionDetectionResult,
    )
