"""Exercises knowledge search (concepts, rules, transcript chunks) against a
real database — no LLM involved, since full-text search never calls one."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.db import get_engine, get_session_factory
from app.models.concept import Concept, ConceptSource
from app.models.enums import (
    RuleCategory,
    RuleEvidenceType,
    RuleStatus,
    SourceStatus,
    SourceType,
    TranscriptStatus,
)
from app.models.project import Project
from app.models.rule import Rule, RuleSource
from app.models.series import Series
from app.models.source import Source, Transcript, TranscriptChunk, Video
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
def knowledge_base(db):
    unique = uuid.uuid4().hex
    user = User(clerk_user_id=f"search-test-{unique}", email=f"search-test-{unique}@example.com")
    db.add(user)
    db.flush()
    project = Project(owner_id=user.id, name="Search Service Test")
    db.add(project)
    db.flush()
    source = Source(
        project_id=project.id,
        source_type=SourceType.YOUTUBE_VIDEO,
        url=f"https://www.youtube.com/watch?v={unique}",
        status=SourceStatus.READY,
    )
    db.add(source)
    db.flush()
    series_a = Series(
        project_id=project.id, source_id=source.id, creator_name="ICT", series_name="Series A"
    )
    series_b = Series(
        project_id=project.id, source_id=source.id, creator_name="ICT", series_name="Series B"
    )
    db.add_all([series_a, series_b])
    db.flush()
    video_a = Video(
        source_id=source.id,
        project_id=project.id,
        series_id=series_a.id,
        youtube_video_id=f"vidA{unique[:8]}",
        title="Order Blocks Explained",
        url="https://www.youtube.com/watch?v=vidA",
        transcript_status=TranscriptStatus.AVAILABLE,
    )
    video_b = Video(
        source_id=source.id,
        project_id=project.id,
        series_id=series_b.id,
        youtube_video_id=f"vidB{unique[:8]}",
        title="Liquidity Sweeps",
        url="https://www.youtube.com/watch?v=vidB",
        transcript_status=TranscriptStatus.AVAILABLE,
    )
    db.add_all([video_a, video_b])
    db.flush()
    transcript_a = Transcript(
        video_id=video_a.id, language="en", is_auto_generated=False, full_text="t"
    )
    db.add(transcript_a)
    db.flush()
    chunk_a = TranscriptChunk(
        transcript_id=transcript_a.id,
        video_id=video_a.id,
        chunk_index=0,
        start_seconds=10.0,
        end_seconds=40.0,
        text=f"An order block forms at the last down candle before a strong move up. [{unique}]",
        content_hash=f"hash-{unique}-a",
    )
    db.add(chunk_a)
    db.flush()

    concept = Concept(
        project_id=project.id,
        name=f"Order Block {unique[:8]}",
        description="A zone of institutional interest formed by the last opposing candle before displacement.",
        confidence=0.9,
        instrument_tags=["NQ"],
    )
    db.add(concept)
    db.flush()
    concept_source = ConceptSource(
        concept_id=concept.id,
        video_id=video_a.id,
        chunk_id=chunk_a.id,
        start_seconds=10.0,
        end_seconds=40.0,
        excerpt=chunk_a.text,
    )
    db.add(concept_source)

    rule = Rule(
        project_id=project.id,
        series_id=series_b.id,
        category=RuleCategory.ENTRY,
        natural_language_rule=(
            f"Enter after a liquidity sweep and displacement below the previous session low. [{unique}]"
        ),
        confidence=0.8,
        status=RuleStatus.EXTRACTED,
        evidence_type=RuleEvidenceType.EXPLICIT,
        instrument_tags=["NQ"],
    )
    db.add(rule)
    db.flush()
    rule_source = RuleSource(
        rule_id=rule.id,
        video_id=video_b.id,
        start_seconds=5.0,
        end_seconds=20.0,
        excerpt="liquidity sweep excerpt",
    )
    db.add(rule_source)
    db.commit()

    return {
        "project": project,
        "series_a": series_a,
        "series_b": series_b,
        "video_a": video_a,
        "video_b": video_b,
        "chunk_a": chunk_a,
        "concept": concept,
        "rule": rule,
        "unique": unique,
    }


def test_search_finds_concept_with_citation(db, knowledge_base):
    kb = knowledge_base
    results = search_service.search_knowledge(
        db, kb["project"].id, "order block", types=("CONCEPT",)
    )
    assert len(results) == 1
    result = results[0]
    assert result.result_type == "CONCEPT"
    assert result.id == kb["concept"].id
    assert len(result.citations) == 1
    assert result.citations[0].video_id == kb["video_a"].id


def test_search_finds_rule_with_citation_and_evidence_type(db, knowledge_base):
    kb = knowledge_base
    results = search_service.search_knowledge(
        db, kb["project"].id, "liquidity sweep", types=("RULE",)
    )
    assert len(results) == 1
    result = results[0]
    assert result.result_type == "RULE"
    assert result.id == kb["rule"].id
    assert result.evidence_type == "EXPLICIT"
    assert result.series_id == kb["series_b"].id
    assert result.citations[0].video_id == kb["video_b"].id


def test_search_finds_raw_transcript_chunk(db, knowledge_base):
    kb = knowledge_base
    results = search_service.search_knowledge(
        db, kb["project"].id, "down candle", types=("TRANSCRIPT",)
    )
    assert len(results) == 1
    result = results[0]
    assert result.result_type == "TRANSCRIPT"
    assert result.id == kb["chunk_a"].id
    assert result.citations[0].video_title == "Order Blocks Explained"


def test_search_series_filter_excludes_other_series(db, knowledge_base):
    kb = knowledge_base
    # The rule lives in series_b; filtering to series_a must exclude it.
    results = search_service.search_knowledge(
        db, kb["project"].id, "liquidity sweep", types=("RULE",), series_id=kb["series_a"].id
    )
    assert results == []


def test_search_merges_result_types_ranked_together(db, knowledge_base):
    kb = knowledge_base
    # "displacement" appears in both the concept description and the rule
    # text — a single call across both types must return both, merged and
    # ranked together (not just whichever type happened to be queried first).
    results = search_service.search_knowledge(db, kb["project"].id, "displacement")
    result_types = {r.result_type for r in results}
    assert "CONCEPT" in result_types
    assert "RULE" in result_types


def test_empty_query_returns_no_results(db, knowledge_base):
    kb = knowledge_base
    assert search_service.search_knowledge(db, kb["project"].id, "   ") == []
