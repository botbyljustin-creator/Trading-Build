"""End-to-end validation of the ICT fixture pipeline (STEP 23 of the ICT
integration spec): every rule traces to a real source, timestamps belong
to the video they claim, AI assumptions can never masquerade as confirmed
teaching, rules from different series stay distinguishable, and a genuine
contradiction is detected and preserved (never silently auto-resolved).

Runs the identical fixture-building code used by
`scripts/seed_ict_fixture.py` (via `build_fixture_project`), under a fresh,
uniquely-named project so it never collides with a project already seeded
in a shared dev database.
"""

from __future__ import annotations

import uuid

import pytest
from scripts.seed_ict_fixture import build_fixture_project
from sqlalchemy import text

from app.core.db import get_engine, get_session_factory
from app.models.concept import Concept
from app.models.enums import ContradictionResolution, RuleEvidenceType, RuleStatus
from app.models.project import Project
from app.models.rule import Contradiction, Rule
from app.models.series import Series
from app.models.source import TranscriptChunk, Video
from app.models.user import User
from app.services import search_service


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
def fixture_project(db) -> Project:
    unique = uuid.uuid4().hex
    user = User(
        clerk_user_id=f"ict-fixture-test-{unique}", email=f"ict-fixture-test-{unique}@example.com"
    )
    db.add(user)
    db.flush()
    return build_fixture_project(db, owner_id=user.id, project_name=f"ICT Fixture Test {unique}")


def test_every_rule_has_at_least_one_source(db, fixture_project):
    rules = db.query(Rule).filter(Rule.project_id == fixture_project.id).all()
    assert len(rules) > 0
    for rule in rules:
        assert len(rule.sources) >= 1, f"Rule {rule.id} has no source citation"


def test_source_video_ids_belong_to_this_project(db, fixture_project):
    project_video_ids = {
        v.id for v in db.query(Video).filter(Video.project_id == fixture_project.id).all()
    }
    rules = db.query(Rule).filter(Rule.project_id == fixture_project.id).all()
    for rule in rules:
        for source in rule.sources:
            assert source.video_id in project_video_ids

    concepts = db.query(Concept).filter(Concept.project_id == fixture_project.id).all()
    for concept in concepts:
        for source in concept.sources:
            assert source.video_id in project_video_ids


def test_citation_timestamps_are_within_a_real_transcript_chunk(db, fixture_project):
    """A citation's [start, end] must actually be covered by some chunk of
    the video it claims to cite — it can't point into empty space."""
    rules = db.query(Rule).filter(Rule.project_id == fixture_project.id).all()
    for rule in rules:
        for source in rule.sources:
            chunks = (
                db.query(TranscriptChunk).filter(TranscriptChunk.video_id == source.video_id).all()
            )
            assert any(
                c.start_seconds <= source.start_seconds and source.end_seconds <= c.end_seconds
                for c in chunks
            ), f"Citation [{source.start_seconds}, {source.end_seconds}] on video {source.video_id} matches no chunk"


def test_ai_assumption_rules_never_masquerade_as_extracted(db, fixture_project):
    rules = db.query(Rule).filter(Rule.project_id == fixture_project.id).all()
    assumption_rules = [r for r in rules if r.evidence_type == RuleEvidenceType.AI_ASSUMPTION]
    assert len(assumption_rules) >= 1
    for rule in assumption_rules:
        assert rule.status == RuleStatus.AI_ASSUMPTION
        assert rule.status != RuleStatus.EXTRACTED


def test_discretionary_rule_is_never_marked_fully_quantifiable(db, fixture_project):
    rules = db.query(Rule).filter(Rule.project_id == fixture_project.id).all()
    discretionary = [r for r in rules if r.evidence_type == RuleEvidenceType.DISCRETIONARY]
    assert len(discretionary) >= 1
    for rule in discretionary:
        assert rule.quantifiability.value == "DISCRETIONARY"


def test_rules_from_different_series_stay_distinguishable(db, fixture_project):
    series_rows = db.query(Series).filter(Series.project_id == fixture_project.id).all()
    assert len(series_rows) == 2
    rules = db.query(Rule).filter(Rule.project_id == fixture_project.id).all()
    series_ids_used = {r.series_id for r in rules}
    assert len(series_ids_used) == 2, "Rules from both series must carry distinct series_id values"

    for series in series_rows:
        scoped = [r for r in rules if r.series_id == series.id]
        assert len(scoped) >= 1
        for other in series_rows:
            if other.id == series.id:
                continue
            assert all(r.series_id != other.id for r in scoped)


def test_cross_series_contradiction_is_detected_and_left_unresolved(db, fixture_project):
    contradictions = (
        db.query(Contradiction).filter(Contradiction.project_id == fixture_project.id).all()
    )
    assert len(contradictions) == 1
    contradiction = contradictions[0]
    assert contradiction.resolution == ContradictionResolution.UNRESOLVED

    rule_a = db.query(Rule).filter(Rule.id == contradiction.rule_a_id).one()
    rule_b = db.query(Rule).filter(Rule.id == contradiction.rule_b_id).one()
    # The two contradicting rules must come from the two different series —
    # this is specifically the "teaching evolved across eras" case, not two
    # rules from the same video disagreeing with each other.
    assert rule_a.series_id != rule_b.series_id

    # The contradiction must never have silently downgraded either rule
    # to REJECTED or silently picked a winner.
    assert rule_a.status == RuleStatus.CONTRADICTORY
    assert rule_b.status == RuleStatus.CONTRADICTORY


def test_search_scoped_to_one_series_excludes_the_other(db, fixture_project):
    series_rows = {
        s.series_name: s
        for s in db.query(Series).filter(Series.project_id == fixture_project.id).all()
    }
    series_2016 = series_rows["ICT 2016 Concepts (SYNTHETIC FIXTURE)"]

    results = search_service.search_knowledge(
        db, fixture_project.id, "retracement", types=("RULE",), series_id=series_2016.id
    )
    assert len(results) == 1
    assert "70%" in results[0].snippet
    assert "62%" not in results[0].snippet
