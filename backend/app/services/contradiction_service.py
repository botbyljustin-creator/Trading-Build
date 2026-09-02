"""Contradiction Analyst orchestration (ARCHITECTURE.md §5.4, Module 7)."""

from __future__ import annotations

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.agents.contradiction_analyst import detect_contradictions
from app.ai.base import LLMProvider
from app.ai.rendering import RuleSummary
from app.models.enums import ContradictionResolution, RuleStatus
from app.models.rule import Contradiction, Rule


def detect_contradictions_for_project(
    db: Session, project_id, provider: LLMProvider
) -> list[Contradiction]:
    rules = (
        db.query(Rule)
        .filter(Rule.project_id == project_id, Rule.status != RuleStatus.REJECTED)
        .all()
    )
    rules_by_id = {str(r.id): r for r in rules}
    summaries = [
        RuleSummary(
            rule_id=str(r.id),
            category=r.category.value,
            natural_language_rule=r.natural_language_rule,
        )
        for r in rules
    ]
    result = detect_contradictions(provider, summaries)

    created: list[Contradiction] = []
    for candidate in result.contradictions:
        rule_a = rules_by_id.get(candidate.rule_a_id)
        rule_b = rules_by_id.get(candidate.rule_b_id)
        if rule_a is None or rule_b is None or rule_a.id == rule_b.id:
            continue  # model referenced an id we didn't give it — ignore rather than guess

        existing = (
            db.query(Contradiction)
            .filter(
                Contradiction.project_id == project_id,
                or_(
                    (Contradiction.rule_a_id == rule_a.id) & (Contradiction.rule_b_id == rule_b.id),
                    (Contradiction.rule_a_id == rule_b.id) & (Contradiction.rule_b_id == rule_a.id),
                ),
            )
            .one_or_none()
        )
        if existing is not None:
            continue

        contradiction = Contradiction(
            project_id=project_id,
            rule_a_id=rule_a.id,
            rule_b_id=rule_b.id,
            explanation=candidate.explanation,
        )
        db.add(contradiction)

        # Only downgrade rules a human hasn't already reviewed — an
        # already-approved rule keeps its status; the contradiction is
        # still recorded so the user can see and resolve the conflict.
        for rule in (rule_a, rule_b):
            if rule.status in (RuleStatus.EXTRACTED, RuleStatus.AMBIGUOUS):
                rule.status = RuleStatus.CONTRADICTORY

        created.append(contradiction)

    db.commit()
    return created


def has_unresolved_contradiction(db: Session, rule_ids: list[uuid.UUID]) -> list[Contradiction]:
    if not rule_ids:
        return []
    return (
        db.query(Contradiction)
        .filter(
            Contradiction.resolution == ContradictionResolution.UNRESOLVED,
            or_(Contradiction.rule_a_id.in_(rule_ids), Contradiction.rule_b_id.in_(rule_ids)),
        )
        .all()
    )
