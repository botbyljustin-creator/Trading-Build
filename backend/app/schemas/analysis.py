"""Structured outputs for the Backtest Analyst and Robustness Analyst
agents (Modules 15, 13-14). Both are constrained to analytical, non-
promissory language — enforced by `app.ai.guardrails.assert_not_promissory`
applied to every string field before the object is trusted."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OverfittingRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class BacktestAnalysis(BaseModel):
    observations: list[str] = Field(
        default_factory=list,
        description="Neutral, falsifiable observations about backtest results "
        "(e.g. session-dependent performance, trade concentration).",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Data/sample-size/assumption caveats the reader should weigh.",
    )


class RobustnessAnalysis(BaseModel):
    overfitting_risk: OverfittingRiskLevel
    reasons: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
