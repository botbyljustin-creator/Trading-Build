"""Model Backtest Readiness Score (STEP 17 of the ICT integration spec).

A creator's catalog rarely yields one strategy — it yields several
candidate "models," one per series/mentorship (see `app.models.series`:
"don't flatten the channel"). Before backtesting any of them, this scores
each series' current rule set on how close it is to backtestable, so the
user can pick where to invest quantification effort first rather than
guessing or backtesting everything at once.

This is deliberately a *pre-compilation* signal over raw extracted rules —
distinct from `app.strategy.completeness.check_completeness`, which grades
one already-compiled `StrategySpecification` against a full field
checklist. A series can score well here (good raw material) long before
anyone has selected rules into a `StrategyVersion`.

Never invents rules to improve a score — an empty category is scored as
missing, not filled in.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.enums import (
    ContradictionResolution,
    Quantifiability,
    RuleCategory,
    RuleEvidenceType,
)
from app.models.rule import Contradiction, Rule
from app.models.series import Series

CORE_CATEGORIES: tuple[RuleCategory, ...] = (
    RuleCategory.ENTRY,
    RuleCategory.STOP_LOSS,
    RuleCategory.TAKE_PROFIT,
    RuleCategory.POSITION_SIZING,
)

UNGROUPED_LABEL = "Ungrouped (no series)"

_SOURCE_SUPPORT_WEIGHT = 30.0
_QUANTIFIABILITY_WEIGHT = 30.0
_COMPLETENESS_WEIGHT = 25.0
_NASDAQ_RELEVANCE_WEIGHT = 15.0
_CONTRADICTION_PENALTY_PER_UNRESOLVED = 5.0

_NASDAQ_TAGS = {"NQ", "NASDAQ_100", "US100", "NAS100"}


@dataclass
class ModelReadiness:
    series_id: uuid.UUID | None
    series_name: str
    creator_name: str | None
    total_rules: int
    explicit_rules: int
    fully_quantifiable_rules: int
    partially_quantifiable_rules: int
    discretionary_rules: int
    nasdaq_relevant_rules: int
    categories_present: list[str] = field(default_factory=list)
    categories_missing: list[str] = field(default_factory=list)
    unresolved_contradictions: int = 0
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)


def _score_one(
    series_id: uuid.UUID | None,
    series_name: str,
    creator_name: str | None,
    rules: list[Rule],
    unresolved_contradiction_rule_ids: set[uuid.UUID],
) -> ModelReadiness:
    total = len(rules)
    explicit = sum(1 for r in rules if r.evidence_type == RuleEvidenceType.EXPLICIT)
    fully_q = sum(1 for r in rules if r.quantifiability == Quantifiability.FULLY_QUANTIFIABLE)
    partially_q = sum(
        1 for r in rules if r.quantifiability == Quantifiability.PARTIALLY_QUANTIFIABLE
    )
    discretionary = sum(1 for r in rules if r.quantifiability == Quantifiability.DISCRETIONARY)
    nasdaq_relevant = sum(1 for r in rules if _NASDAQ_TAGS.intersection(r.instrument_tags))

    categories_present_set = {r.category for r in rules}
    categories_present = sorted(c.value for c in categories_present_set)
    categories_missing = sorted(c.value for c in CORE_CATEGORIES if c not in categories_present_set)

    unresolved = sum(1 for r in rules if r.id in unresolved_contradiction_rule_ids)

    if total == 0:
        return ModelReadiness(
            series_id=series_id,
            series_name=series_name,
            creator_name=creator_name,
            total_rules=0,
            explicit_rules=0,
            fully_quantifiable_rules=0,
            partially_quantifiable_rules=0,
            discretionary_rules=0,
            nasdaq_relevant_rules=0,
            categories_present=[],
            categories_missing=[c.value for c in CORE_CATEGORIES],
            unresolved_contradictions=0,
            score=0.0,
            score_breakdown={
                "source_support": 0.0,
                "quantifiability": 0.0,
                "completeness": 0.0,
                "nasdaq_relevance": 0.0,
                "contradiction_penalty": 0.0,
            },
        )

    source_support = (explicit / total) * _SOURCE_SUPPORT_WEIGHT
    quantifiability_score = ((fully_q * 1.0 + partially_q * 0.5) / total) * _QUANTIFIABILITY_WEIGHT
    completeness = (
        len(categories_present_set & set(CORE_CATEGORIES)) / len(CORE_CATEGORIES)
    ) * _COMPLETENESS_WEIGHT
    nasdaq_relevance = (nasdaq_relevant / total) * _NASDAQ_RELEVANCE_WEIGHT
    penalty = min(
        unresolved * _CONTRADICTION_PENALTY_PER_UNRESOLVED, source_support + quantifiability_score
    )

    raw_score = source_support + quantifiability_score + completeness + nasdaq_relevance - penalty
    score = round(max(0.0, min(100.0, raw_score)), 1)

    return ModelReadiness(
        series_id=series_id,
        series_name=series_name,
        creator_name=creator_name,
        total_rules=total,
        explicit_rules=explicit,
        fully_quantifiable_rules=fully_q,
        partially_quantifiable_rules=partially_q,
        discretionary_rules=discretionary,
        nasdaq_relevant_rules=nasdaq_relevant,
        categories_present=categories_present,
        categories_missing=categories_missing,
        unresolved_contradictions=unresolved,
        score=score,
        score_breakdown={
            "source_support": round(source_support, 1),
            "quantifiability": round(quantifiability_score, 1),
            "completeness": round(completeness, 1),
            "nasdaq_relevance": round(nasdaq_relevance, 1),
            "contradiction_penalty": round(-penalty, 1),
        },
    )


def compute_model_readiness(db: Session, project_id: uuid.UUID) -> list[ModelReadiness]:
    """One score per series in the project, plus an `UNGROUPED_LABEL` bucket
    for any rules with no series (never merged into a named series)."""
    rules = db.query(Rule).filter(Rule.project_id == project_id).all()
    series_rows = db.query(Series).filter(Series.project_id == project_id).all()
    series_by_id = {s.id: s for s in series_rows}

    unresolved_contradictions = (
        db.query(Contradiction)
        .filter(
            Contradiction.project_id == project_id,
            Contradiction.resolution == ContradictionResolution.UNRESOLVED,
        )
        .all()
    )
    unresolved_rule_ids: set[uuid.UUID] = set()
    for c in unresolved_contradictions:
        unresolved_rule_ids.add(c.rule_a_id)
        unresolved_rule_ids.add(c.rule_b_id)

    rules_by_series: dict[uuid.UUID | None, list[Rule]] = {}
    for r in rules:
        rules_by_series.setdefault(r.series_id, []).append(r)

    results: list[ModelReadiness] = []
    for series_id, series_rules in rules_by_series.items():
        if series_id is None:
            results.append(
                _score_one(None, UNGROUPED_LABEL, None, series_rules, unresolved_rule_ids)
            )
        else:
            series = series_by_id.get(series_id)
            series_name = series.series_name if series else "Unknown series"
            creator_name = series.creator_name if series else None
            results.append(
                _score_one(series_id, series_name, creator_name, series_rules, unresolved_rule_ids)
            )

    results.sort(key=lambda m: m.score, reverse=True)
    return results
