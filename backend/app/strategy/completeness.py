"""Strategy Auditor (deterministic — ARCHITECTURE.md §5.6, Module 6).

Never invents a default for a missing field. `check_completeness` only
reports what is present vs. absent against the required-field checklist.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.strategy_spec import StrategySpecification


@dataclass(frozen=True)
class RequiredField:
    key: str
    question: str
    is_present: Callable[[StrategySpecification], bool]


REQUIRED_FIELDS: list[RequiredField] = [
    RequiredField("market", "What market?", lambda s: bool(s.instrument.market_description)),
    RequiredField("timeframe", "What timeframe?", lambda s: bool(s.instrument.timeframe)),
    RequiredField("session", "What trading session?", lambda s: s.session is not None),
    RequiredField("bias", "How is directional bias determined?", lambda s: bool(s.bias_rule)),
    RequiredField("setup", "What creates a setup?", lambda s: bool(s.setup_rule)),
    RequiredField("entry", "What triggers entry?", lambda s: bool(s.entry_rule)),
    RequiredField("stop", "Where is the stop?", lambda s: s.stop_loss is not None),
    RequiredField("target", "How is the target determined?", lambda s: s.take_profit is not None),
    RequiredField("risk", "How much is risked per trade?", lambda s: s.position_sizing is not None),
    RequiredField(
        "invalidation", "What invalidates the setup?", lambda s: bool(s.invalidation_rule)
    ),
    RequiredField(
        "multiple_positions",
        "Can multiple positions exist at once?",
        lambda s: s.allow_multiple_concurrent_positions is not None,
    ),
    RequiredField(
        "overnight",
        "Can trades occur overnight?",
        lambda s: s.allow_overnight_positions is not None,
    ),
    RequiredField(
        "max_trades_per_day", "Maximum trades per day?", lambda s: s.max_trades_per_day is not None
    ),
    RequiredField(
        "direction",
        "Long only, short only, or both?",
        lambda s: s.allow_long is not None and s.allow_short is not None,
    ),
]


@dataclass(frozen=True)
class CompletenessReport:
    score_pct: float
    missing: list[str]  # human-readable questions for fields not present
    missing_keys: list[str]


def check_completeness(spec: StrategySpecification) -> CompletenessReport:
    missing: list[str] = []
    missing_keys: list[str] = []
    present_count = 0
    for field in REQUIRED_FIELDS:
        if field.is_present(spec):
            present_count += 1
        else:
            missing.append(field.question)
            missing_keys.append(field.key)
    score = round(100.0 * present_count / len(REQUIRED_FIELDS), 1)
    return CompletenessReport(score_pct=score, missing=missing, missing_keys=missing_keys)
