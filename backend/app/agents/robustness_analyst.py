"""Robustness Analyst agent (ARCHITECTURE.md §5.9, Modules 13-14)."""

from __future__ import annotations

import json

from app.ai.base import LLMProvider
from app.ai.guardrails import sanitize_string_list
from app.ai.prompts.agents import ROBUSTNESS_ANALYST_SYSTEM_PROMPT
from app.schemas.analysis import RobustnessAnalysis

INSTRUCTION = (
    "Assess the robustness of this strategy from the following in-sample/"
    "out-of-sample, walk-forward, sensitivity, and Monte Carlo results, and "
    "the optimization footprint (parameters optimized, combinations tested, "
    "number of historical trades). Assign an overfitting risk with reasons."
)


def analyze_robustness(provider: LLMProvider, robustness_data: dict) -> RobustnessAnalysis:
    result = provider.generate_structured(
        system_prompt=ROBUSTNESS_ANALYST_SYSTEM_PROMPT,
        source_content=json.dumps(robustness_data, default=str, indent=2),
        instruction=INSTRUCTION,
        response_model=RobustnessAnalysis,
    )
    return RobustnessAnalysis(
        overfitting_risk=result.overfitting_risk,
        reasons=sanitize_string_list(result.reasons),
        observations=sanitize_string_list(result.observations),
    )
