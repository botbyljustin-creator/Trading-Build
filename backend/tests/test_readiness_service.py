"""Exercises the Model Backtest Readiness Score (STEP 17) against a real
database — no LLM involved, this is pure scoring logic over persisted
rules."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.db import get_engine, get_session_factory
from app.models.enums import (
    ContradictionResolution,
    Quantifiability,
    RuleCategory,
    RuleEvidenceType,
)
from app.models.project import Project
from app.models.rule import Contradiction, Rule
from app.models.series import Series
from app.models.user import User
from app.services.readiness_service import UNGROUPED_LABEL, compute_model_readiness


def _database_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _database_available(), reason="Requires a reachable Postgres database."
)


@pytest.fixture
def db():
    session = get_session_factory()()
    yield session
    session.close()


@pytest.fixture
def project(db):
    unique = uuid.uuid4().hex
    user = User(
        clerk_user_id=f"readiness-test-{unique}", email=f"readiness-test-{unique}@example.com"
    )
    db.add(user)
    db.flush()
    project = Project(owner_id=user.id, name="Readiness Service Test")
    db.add(project)
    db.flush()
    return project


def _rule(project_id, series_id, category, evidence_type, quantifiability, tags):
    return Rule(
        project_id=project_id,
        series_id=series_id,
        category=category,
        natural_language_rule=f"fixture rule {uuid.uuid4().hex[:6]}",
        confidence=0.8,
        evidence_type=evidence_type,
        quantifiability=quantifiability,
        instrument_tags=tags,
    )


def test_series_with_no_rules_is_excluded(db, project):
    series = Series(project_id=project.id, creator_name="C", series_name="Empty Series")
    db.add(series)
    db.commit()
    results = compute_model_readiness(db, project.id)
    assert results == []


def test_fully_complete_series_scores_100(db, project):
    series = Series(project_id=project.id, creator_name="C", series_name="Complete Series")
    db.add(series)
    db.flush()
    for category in (
        RuleCategory.ENTRY,
        RuleCategory.STOP_LOSS,
        RuleCategory.TAKE_PROFIT,
        RuleCategory.POSITION_SIZING,
    ):
        db.add(
            _rule(
                project.id,
                series.id,
                category,
                RuleEvidenceType.EXPLICIT,
                Quantifiability.FULLY_QUANTIFIABLE,
                ["NQ"],
            )
        )
    db.commit()

    results = compute_model_readiness(db, project.id)
    assert len(results) == 1
    result = results[0]
    assert result.series_name == "Complete Series"
    assert result.categories_missing == []
    assert result.score == 100.0


def test_discretionary_and_missing_categories_lower_the_score(db, project):
    series = Series(project_id=project.id, creator_name="C", series_name="Sparse Series")
    db.add(series)
    db.flush()
    db.add(
        _rule(
            project.id,
            series.id,
            RuleCategory.SETUP,
            RuleEvidenceType.DISCRETIONARY,
            Quantifiability.DISCRETIONARY,
            [],
        )
    )
    db.commit()

    results = compute_model_readiness(db, project.id)
    assert len(results) == 1
    result = results[0]
    assert result.score < 30.0
    assert set(result.categories_missing) == {
        "ENTRY",
        "STOP_LOSS",
        "TAKE_PROFIT",
        "POSITION_SIZING",
    }


def test_ungrouped_rules_form_their_own_bucket(db, project):
    db.add(
        _rule(
            project.id,
            None,
            RuleCategory.ENTRY,
            RuleEvidenceType.EXPLICIT,
            Quantifiability.FULLY_QUANTIFIABLE,
            [],
        )
    )
    db.commit()
    results = compute_model_readiness(db, project.id)
    assert len(results) == 1
    assert results[0].series_id is None
    assert results[0].series_name == UNGROUPED_LABEL


def test_unresolved_contradiction_penalizes_score(db, project):
    series = Series(project_id=project.id, creator_name="C", series_name="Contradicted Series")
    db.add(series)
    db.flush()
    rule_a = _rule(
        project.id,
        series.id,
        RuleCategory.ENTRY,
        RuleEvidenceType.EXPLICIT,
        Quantifiability.FULLY_QUANTIFIABLE,
        ["NQ"],
    )
    rule_b = _rule(
        project.id,
        series.id,
        RuleCategory.ENTRY,
        RuleEvidenceType.EXPLICIT,
        Quantifiability.FULLY_QUANTIFIABLE,
        ["NQ"],
    )
    db.add_all([rule_a, rule_b])
    db.flush()

    without_contradiction = compute_model_readiness(db, project.id)[0].score

    db.add(
        Contradiction(
            project_id=project.id,
            rule_a_id=rule_a.id,
            rule_b_id=rule_b.id,
            explanation="fixture contradiction",
            resolution=ContradictionResolution.UNRESOLVED,
        )
    )
    db.commit()

    with_contradiction = compute_model_readiness(db, project.id)[0]
    assert with_contradiction.unresolved_contradictions == 2  # both rules flagged
    assert with_contradiction.score < without_contradiction


def test_resolved_contradiction_does_not_penalize(db, project):
    series = Series(project_id=project.id, creator_name="C", series_name="Resolved Series")
    db.add(series)
    db.flush()
    rule_a = _rule(
        project.id,
        series.id,
        RuleCategory.ENTRY,
        RuleEvidenceType.EXPLICIT,
        Quantifiability.FULLY_QUANTIFIABLE,
        ["NQ"],
    )
    rule_b = _rule(
        project.id,
        series.id,
        RuleCategory.ENTRY,
        RuleEvidenceType.EXPLICIT,
        Quantifiability.FULLY_QUANTIFIABLE,
        ["NQ"],
    )
    db.add_all([rule_a, rule_b])
    db.flush()
    db.add(
        Contradiction(
            project_id=project.id,
            rule_a_id=rule_a.id,
            rule_b_id=rule_b.id,
            explanation="fixture contradiction",
            resolution=ContradictionResolution.USE_A,
        )
    )
    db.commit()

    result = compute_model_readiness(db, project.id)[0]
    assert result.unresolved_contradictions == 0
