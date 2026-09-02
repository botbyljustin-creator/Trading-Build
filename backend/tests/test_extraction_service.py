"""Exercises the real extraction pipeline (concept + rule persistence,
evidence_type -> status mapping, series propagation, instrument tagging,
and content-hash caching) against a real database with a fake LLM
provider — no network, no real API key required.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.ai.base import LLMProvider
from app.core.db import get_engine, get_session_factory
from app.models.concept import Concept
from app.models.enums import RuleCategory, RuleStatus, SourceStatus, SourceType, TranscriptStatus
from app.models.extraction_cache import ExtractionCache
from app.models.project import Project
from app.models.series import Series
from app.models.source import Source, Transcript, TranscriptChunk, Video
from app.models.user import User
from app.schemas.citations import SourceCitation
from app.schemas.concept import ConceptExtractionResult, ExtractedConcept
from app.schemas.rule import ExtractedRule, RuleExtractionResult
from app.services import extraction_service


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


class FakeLLMProvider(LLMProvider):
    name = "fake"

    def __init__(self):
        self.calls = 0

    def generate_structured(
        self, *, system_prompt, source_content, instruction, response_model, max_tokens=4096
    ):
        self.calls += 1
        import re

        match = re.search(r"\[video_id=(\S+) start=([\d.]+) end=([\d.]+)\]", source_content)
        video_id, start, end = match.group(1), float(match.group(2)), float(match.group(3))
        citation = SourceCitation(
            video_id=video_id,
            start_seconds=start,
            end_seconds=end,
            excerpt="ICT-style fixture excerpt.",
        )

        if response_model is ConceptExtractionResult:
            return ConceptExtractionResult(
                concepts=[
                    ExtractedConcept(
                        name="Fair Value Gap",
                        description="A three-candle imbalance in price delivery.",
                        confidence=0.9,
                        sources=[citation],
                    )
                ]
            )
        if response_model is RuleExtractionResult:
            return RuleExtractionResult(
                rules=[
                    ExtractedRule(
                        category=RuleCategory.ENTRY,
                        natural_language_rule="Enter on NASDAQ NQ when price fills the fair value gap.",
                        confidence=0.85,
                        evidence_type="EXPLICIT",
                        quantifiability="PARTIALLY_QUANTIFIABLE",
                        sources=[citation],
                    ),
                    ExtractedRule(
                        category=RuleCategory.BIAS,
                        natural_language_rule="Inferred: bias follows the higher timeframe FVG.",
                        confidence=0.4,
                        evidence_type="AI_ASSUMPTION",
                        quantifiability="DISCRETIONARY",
                        sources=[citation],
                    ),
                ]
            )
        raise AssertionError(f"Unexpected response_model: {response_model}")

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


@pytest.fixture
def db():
    session = get_session_factory()()
    yield session
    session.close()


@pytest.fixture
def project_with_video(db):
    unique = uuid.uuid4().hex
    user = User(clerk_user_id=f"extract-test-{unique}", email=f"extract-test-{unique}@example.com")
    db.add(user)
    db.flush()
    project = Project(owner_id=user.id, name="Extraction Service Test")
    db.add(project)
    db.flush()
    source = Source(
        project_id=project.id,
        source_type=SourceType.YOUTUBE_VIDEO,
        url="https://www.youtube.com/watch?v=fixture001",
        status=SourceStatus.READY,
    )
    db.add(source)
    db.flush()
    series = Series(
        project_id=project.id,
        source_id=source.id,
        creator_name="Inner Circle Trader",
        series_name="Fixture Series",
        youtube_playlist_id="PL_fixture",
    )
    db.add(series)
    db.flush()
    video = Video(
        source_id=source.id,
        project_id=project.id,
        series_id=series.id,
        position_in_series=0,
        youtube_video_id="fixture001",
        title="Fixture Video",
        url="https://www.youtube.com/watch?v=fixture001",
        transcript_status=TranscriptStatus.AVAILABLE,
    )
    db.add(video)
    db.flush()
    transcript = Transcript(
        video_id=video.id, language="en", is_auto_generated=False, full_text="fixture text"
    )
    db.add(transcript)
    db.flush()
    chunk = TranscriptChunk(
        transcript_id=transcript.id,
        video_id=video.id,
        chunk_index=0,
        start_seconds=0.0,
        end_seconds=45.0,
        text=f"Fixture transcript chunk about NASDAQ NQ fair value gaps. [{unique}]",
        content_hash=f"fixturehash-{unique}",
    )
    db.add(chunk)
    db.commit()
    return project, video


def test_extract_concepts_persists_with_instrument_tags(db, project_with_video):
    project, _video = project_with_video
    provider = FakeLLMProvider()
    concepts = extraction_service.extract_concepts_for_project(db, project.id, provider)
    assert len(concepts) == 1
    stored = db.query(Concept).filter(Concept.project_id == project.id).one()
    assert stored.name == "Fair Value Gap"
    assert len(stored.sources) == 1


def test_extract_rules_maps_evidence_type_to_status_and_propagates_series(db, project_with_video):
    project, video = project_with_video
    provider = FakeLLMProvider()
    rules = extraction_service.extract_rules_for_project(db, project.id, provider)
    assert len(rules) == 2

    explicit_rule = next(r for r in rules if r.evidence_type.value == "EXPLICIT")
    assumption_rule = next(r for r in rules if r.evidence_type.value == "AI_ASSUMPTION")

    assert explicit_rule.status == RuleStatus.EXTRACTED
    assert assumption_rule.status == RuleStatus.AI_ASSUMPTION  # never silently promoted
    assert explicit_rule.series_id == video.series_id
    assert explicit_rule.quantifiability.value == "PARTIALLY_QUANTIFIABLE"
    assert "NQ" in explicit_rule.instrument_tags


def test_repeated_extraction_on_unchanged_content_hits_cache(db, project_with_video):
    project, _video = project_with_video
    provider = FakeLLMProvider()
    baseline = (
        db.query(ExtractionCache).filter(ExtractionCache.extractor_name == "rule_extractor").count()
    )

    extraction_service.extract_rules_for_project(db, project.id, provider)
    assert provider.calls == 1

    # Re-running against the exact same (unchanged) chunk must not call the
    # LLM again — it should be served from app.models.extraction_cache.
    extraction_service.extract_rules_for_project(db, project.id, provider)
    assert provider.calls == 1

    new_rows = (
        db.query(ExtractionCache).filter(ExtractionCache.extractor_name == "rule_extractor").count()
        - baseline
    )
    assert new_rows == 1
