"""Backtest Analyst agent (ARCHITECTURE.md §5.8, Module 15)."""

from __future__ import annotations

import json

from app.ai.base import LLMProvider
from app.ai.guardrails import sanitize_string_list
from app.ai.prompts.agents import BACKTEST_ANALYST_SYSTEM_PROMPT
from app.schemas.analysis import BacktestAnalysis

INSTRUCTION = (
    "Analyze the following backtest metrics and trade statistics. Produce "
    "specific, falsifiable observations and caveats."
)


def analyze_backtest(provider: LLMProvider, metrics: dict) -> BacktestAnalysis:
    result = provider.generate_structured(
        system_prompt=BACKTEST_ANALYST_SYSTEM_PROMPT,
        source_content=json.dumps(metrics, default=str, indent=2),
        instruction=INSTRUCTION,
        response_model=BacktestAnalysis,
    )
    return BacktestAnalysis(
        observations=sanitize_string_list(result.observations),
        caveats=sanitize_string_list(result.caveats),
    )
