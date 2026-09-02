"""Seeds a small, clearly-labeled SYNTHETIC FIXTURE dataset shaped like
Inner Circle Trader (ICT) content, across two distinct series, and runs it
through the real ingestion -> extraction -> contradiction-detection ->
search pipeline. Then prints a validation report.

Why synthetic and not real ICT transcripts: this sandbox's network policy
blocks youtube.com (see CURRENT_STATE.md), so a live channel/playlist
ingestion pass cannot run here. `app/services/manual_import_service.py`
exists specifically so a user with YouTube access can paste in real
`youtube_transcript_api` output for real ICT videos; when that happens,
this exact same pipeline runs unchanged against real source material. This
script's only job is to prove the pipeline itself is correct — the series
hierarchy stays separate, evidence types are classified honestly,
discretionary rules never get silently upgraded, and a genuine contradiction
between two "eras" of ICT's Optimal Trade Entry teaching (a documented,
expected kind of evolution across ICT's catalog) is detected and preserved
rather than merged away.

No LLM API call is made or required: a `ScriptedICTFixtureProvider`
deterministically returns what a competent extractor would plausibly
produce for this exact fixture text, so the persistence/classification/
contradiction logic under test is the same code path used with a real
provider (see app/ai/base.py's `LLMProvider` interface).

Run with: `python scripts/seed_ict_fixture.py` (repeat runs are a no-op if
the fixture project already exists — delete it first to reseed).
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.base import LLMProvider  # noqa: E402
from app.core.db import get_session_factory  # noqa: E402
from app.ingestion.chunking import TranscriptSegment  # noqa: E402
from app.models.concept import Concept  # noqa: E402
from app.models.enums import RuleCategory  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.rule import Contradiction, Rule  # noqa: E402
from app.models.series import Series  # noqa: E402
from app.models.source import Video  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.citations import SourceCitation  # noqa: E402
from app.schemas.concept import ConceptExtractionResult, ExtractedConcept  # noqa: E402
from app.schemas.contradiction import (  # noqa: E402
    ContradictionCandidate,
    ContradictionDetectionResult,
)
from app.schemas.rule import ExtractedRule, RuleExtractionResult  # noqa: E402
from app.security.clerk import DEV_USER_CLERK_ID, DEV_USER_EMAIL  # noqa: E402
from app.services import contradiction_service, extraction_service, search_service  # noqa: E402
from app.services.manual_import_service import import_manual_video  # noqa: E402

FIXTURE_PROJECT_NAME = "[SYNTHETIC FIXTURE] ICT Pipeline Validation Set"

SERIES_2022 = "ICT Mentorship 2022 (SYNTHETIC FIXTURE)"
SERIES_2016 = "ICT 2016 Concepts (SYNTHETIC FIXTURE)"
FIXTURE_DISCLAIMER = "[SYNTHETIC FIXTURE — not a verbatim quote, for pipeline validation only]"


class ScriptedICTFixtureProvider(LLMProvider):
    """Deterministic stand-in for a real LLM provider. Every method
    inspects the exact rendered prompt content (the same `source_content`
    a real provider would receive) and returns a fixed, hand-authored
    result for this fixture — it never invents anything beyond what's
    scripted here."""

    name = "scripted-ict-fixture"

    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(
        self, *, system_prompt, source_content, instruction, response_model, max_tokens=4096
    ):
        self.calls += 1
        if response_model is ConceptExtractionResult:
            return self._concepts(source_content)
        if response_model is RuleExtractionResult:
            return self._rules(source_content)
        if response_model is ContradictionDetectionResult:
            return self._contradictions(source_content)
        raise AssertionError(
            f"ScriptedICTFixtureProvider has no canned response for {response_model}"
        )

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    @staticmethod
    def _citation(source_content: str) -> SourceCitation:
        match = re.search(
            r"\[video_id=(\S+) start=([\d.]+) end=([\d.]+)\]\n(.*)", source_content, re.DOTALL
        )
        video_id, start, end, text = (
            match.group(1),
            float(match.group(2)),
            float(match.group(3)),
            match.group(4),
        )
        return SourceCitation(
            video_id=video_id, start_seconds=start, end_seconds=end, excerpt=text.strip()[:500]
        )

    def _concepts(self, source_content: str) -> ConceptExtractionResult:
        citation = self._citation(source_content)
        lower = source_content.lower()
        if "order block" in lower:
            return ConceptExtractionResult(
                concepts=[
                    ExtractedConcept(
                        name="Order Block",
                        description="The last opposing candle before a strong displacement move, treated as a zone of institutional interest.",
                        confidence=0.85,
                        sources=[citation],
                    ),
                    ExtractedConcept(
                        name="Fair Value Gap",
                        description="A three-candle imbalance in price delivery left behind by a strong directional move.",
                        confidence=0.85,
                        sources=[citation],
                    ),
                ]
            )
        if "62%" in source_content:
            return ConceptExtractionResult(
                concepts=[
                    ExtractedConcept(
                        name="Optimal Trade Entry (2022 model)",
                        description="A retracement zone used to time entries after a market structure shift, defined here as 62%-79%.",
                        confidence=0.8,
                        sources=[citation],
                    )
                ]
            )
        if "70%" in source_content:
            return ConceptExtractionResult(
                concepts=[
                    ExtractedConcept(
                        name="Optimal Trade Entry (2016 model)",
                        description="An earlier articulation of the retracement entry zone, defined here as 70%-88% — a different range than the 2022 model.",
                        confidence=0.75,
                        sources=[citation],
                    )
                ]
            )
        return ConceptExtractionResult(concepts=[])

    def _rules(self, source_content: str) -> RuleExtractionResult:
        citation = self._citation(source_content)
        lower = source_content.lower()
        if "order block" in lower:
            return RuleExtractionResult(
                rules=[
                    ExtractedRule(
                        category=RuleCategory.ENTRY,
                        natural_language_rule=(
                            "Enter long when price returns into a bullish Fair Value Gap formed during "
                            "the London or New York kill zone, provided a bullish order block sits below "
                            "it, on NASDAQ NQ."
                        ),
                        confidence=0.8,
                        evidence_type="EXPLICIT",
                        quantifiability="PARTIALLY_QUANTIFIABLE",
                        sources=[citation],
                    ),
                    ExtractedRule(
                        category=RuleCategory.CONFIRMATION,
                        natural_language_rule=(
                            "Inferred: prefer the Fair Value Gap closest to a freshly formed order block "
                            "over older, previously mitigated imbalances."
                        ),
                        confidence=0.35,
                        evidence_type="AI_ASSUMPTION",
                        quantifiability="DISCRETIONARY",
                        sources=[citation],
                    ),
                ]
            )
        if "62%" in source_content:
            return RuleExtractionResult(
                rules=[
                    ExtractedRule(
                        category=RuleCategory.ENTRY,
                        natural_language_rule=(
                            "Enter within the 62% to 79% Fibonacci retracement zone of the most recent "
                            "dealing-range swing before continuation."
                        ),
                        confidence=0.85,
                        evidence_type="EXPLICIT",
                        quantifiability="FULLY_QUANTIFIABLE",
                        sources=[citation],
                    )
                ]
            )
        if "70%" in source_content:
            return RuleExtractionResult(
                rules=[
                    ExtractedRule(
                        category=RuleCategory.ENTRY,
                        natural_language_rule=(
                            "Enter within the 70% to 88% retracement zone of the prior dealing-range swing."
                        ),
                        confidence=0.8,
                        evidence_type="EXPLICIT",
                        quantifiability="FULLY_QUANTIFIABLE",
                        sources=[citation],
                    )
                ]
            )
        if "judgment" in lower:
            return RuleExtractionResult(
                rules=[
                    ExtractedRule(
                        category=RuleCategory.SETUP,
                        natural_language_rule=(
                            "Wait for a clear shift in market structure, judged by eye rather than a fixed "
                            "candle count or price threshold, before considering an entry."
                        ),
                        confidence=0.5,
                        evidence_type="DISCRETIONARY",
                        quantifiability="DISCRETIONARY",
                        sources=[citation],
                    )
                ]
            )
        return RuleExtractionResult(rules=[])

    def _contradictions(self, source_content: str) -> ContradictionDetectionResult:
        pattern = re.compile(
            r"\[rule_id=(\S+) category=\S+\]\n(.*?)(?=\n\n\[rule_id=|\Z)", re.DOTALL
        )
        id_62, id_70 = None, None
        for rule_id, text in pattern.findall(source_content):
            if "62%" in text:
                id_62 = rule_id
            if "70%" in text:
                id_70 = rule_id
        if id_62 and id_70:
            return ContradictionDetectionResult(
                contradictions=[
                    ContradictionCandidate(
                        rule_a_id=id_62,
                        rule_b_id=id_70,
                        explanation=(
                            "Two different Optimal Trade Entry retracement ranges are taught across "
                            "series: 62%-79% (2022 model) vs 70%-88% (2016 model). This reflects the "
                            "teaching evolving over time, not the same rule stated twice — they must not "
                            "be silently merged into one."
                        ),
                    )
                ]
            )
        return ContradictionDetectionResult(contradictions=[])


def _seg(text: str) -> list[TranscriptSegment]:
    return [TranscriptSegment(start=0.0, duration=50.0, text=f"{FIXTURE_DISCLAIMER} {text}")]


def build_fixture_project(db, *, owner_id, project_name: str) -> Project:
    """Creates one fixture project with the 4-video / 2-series ICT-style
    dataset and runs it through concept extraction, rule extraction, and
    contradiction detection using `ScriptedICTFixtureProvider`. Factored out
    of `seed()` so `tests/test_ict_fixture_pipeline.py` can exercise the
    exact same fixture under a fresh, isolated project name."""
    project = Project(
        owner_id=owner_id,
        name=project_name,
        description=(
            "Synthetic, clearly-labeled ICT-style fixture data used to validate the ingestion -> "
            "extraction -> contradiction -> search pipeline while youtube.com is network-blocked. "
            "See scripts/seed_ict_fixture.py."
        ),
    )
    db.add(project)
    db.flush()

    import_manual_video(
        db,
        project_id=project.id,
        youtube_video_id="ICTFIX0001",
        url="https://example.invalid/ICTFIX0001",
        title="[SYNTHETIC FIXTURE] Order Blocks & Fair Value Gaps",
        channel_name="Inner Circle Trader (fixture)",
        creator_name="Inner Circle Trader (fixture)",
        series_name=SERIES_2022,
        youtube_playlist_id="FIXTURE_PL_2022",
        position_in_series=0,
        segments=_seg(
            "An order block is the last opposing candle before a strong displacement move, and it "
            "often lines up with a fair value gap. Wait for price to return into the fair value gap "
            "during the London or New York kill zone, with a bullish order block sitting below it, "
            "before entering long on NASDAQ NQ."
        ),
    )
    import_manual_video(
        db,
        project_id=project.id,
        youtube_video_id="ICTFIX0002",
        url="https://example.invalid/ICTFIX0002",
        title="[SYNTHETIC FIXTURE] Optimal Trade Entry — 2022 model",
        channel_name="Inner Circle Trader (fixture)",
        creator_name="Inner Circle Trader (fixture)",
        series_name=SERIES_2022,
        youtube_playlist_id="FIXTURE_PL_2022",
        position_in_series=1,
        segments=_seg(
            "Optimal trade entry is the 62% to 79% Fibonacci retracement zone of the most recent "
            "dealing-range swing, and it's where you look to enter before continuation."
        ),
    )
    import_manual_video(
        db,
        project_id=project.id,
        youtube_video_id="ICTFIX0003",
        url="https://example.invalid/ICTFIX0003",
        title="[SYNTHETIC FIXTURE] Market Structure Judgment Calls",
        channel_name="Inner Circle Trader (fixture)",
        creator_name="Inner Circle Trader (fixture)",
        series_name=SERIES_2022,
        youtube_playlist_id="FIXTURE_PL_2022",
        position_in_series=2,
        segments=_seg(
            "Before you consider an entry, wait for a clear shift in market structure — you have to "
            "read the chart and use your own judgment here, there's no fixed candle count I can give you."
        ),
    )
    import_manual_video(
        db,
        project_id=project.id,
        youtube_video_id="ICTFIX0004",
        url="https://example.invalid/ICTFIX0004",
        title="[SYNTHETIC FIXTURE] Optimal Trade Entry — 2016 model",
        channel_name="Inner Circle Trader (fixture)",
        creator_name="Inner Circle Trader (fixture)",
        series_name=SERIES_2016,
        youtube_playlist_id="FIXTURE_PL_2016",
        position_in_series=0,
        segments=_seg(
            "Back then, optimal trade entry was the 70% to 88% retracement zone of the prior "
            "dealing-range swing — a different range than what gets taught later on."
        ),
    )

    provider = ScriptedICTFixtureProvider()
    extraction_service.extract_concepts_for_project(db, project.id, provider)
    extraction_service.extract_rules_for_project(db, project.id, provider)
    contradiction_service.detect_contradictions_for_project(db, project.id, provider)
    return project


def seed() -> uuid.UUID | None:
    db = get_session_factory()()

    existing = db.query(Project).filter(Project.name == FIXTURE_PROJECT_NAME).one_or_none()
    if existing is not None:
        print(
            f"Fixture project already exists ({existing.id}) — skipping. Delete it first to reseed."
        )
        db.close()
        return existing.id

    user = db.query(User).filter(User.clerk_user_id == DEV_USER_CLERK_ID).one_or_none()
    if user is None:
        user = User(clerk_user_id=DEV_USER_CLERK_ID, email=DEV_USER_EMAIL, display_name="Dev User")
        db.add(user)
        db.flush()

    project = build_fixture_project(db, owner_id=user.id, project_name=FIXTURE_PROJECT_NAME)
    print(f"Seeded fixture project {project.id} ({FIXTURE_PROJECT_NAME})")
    db.close()
    return project.id


def report(project_id) -> None:
    db = get_session_factory()()
    project = db.query(Project).filter(Project.id == project_id).one()
    videos = db.query(Video).filter(Video.project_id == project.id).order_by(Video.title).all()
    series_rows = db.query(Series).filter(Series.project_id == project.id).all()
    concepts = db.query(Concept).filter(Concept.project_id == project.id).all()
    rules = db.query(Rule).filter(Rule.project_id == project.id).all()
    contradictions = db.query(Contradiction).filter(Contradiction.project_id == project.id).all()
    series_by_id = {s.id: s for s in series_rows}

    lines: list[str] = []

    def out(line: str = "") -> None:
        lines.append(line)
        print(line)

    out("=" * 78)
    out(f"ICT PIPELINE VALIDATION REPORT — {project.name}")
    out("=" * 78)

    out("\n1. VIDEOS INGESTED")
    for v in videos:
        series_label = series_by_id[v.series_id].series_name if v.series_id else "(no series)"
        out(
            f"  - {v.title}  [series: {series_label}]  transcript_status={v.transcript_status.value}"
        )

    out("\n2. CONCEPTS EXTRACTED")
    for c in concepts:
        out(
            f"  - {c.name}  (confidence={c.confidence:.2f}, instrument_tags={c.instrument_tags}, sources={len(c.sources)})"
        )

    out("\n3. EXECUTABLE RULES (EXPLICIT + FULLY or PARTIALLY QUANTIFIABLE)")
    executable = [
        r
        for r in rules
        if r.evidence_type.value == "EXPLICIT"
        and r.quantifiability
        and r.quantifiability.value != "DISCRETIONARY"
    ]
    for r in executable:
        series_label = series_by_id[r.series_id].series_name if r.series_id else "(no series)"
        out(f"  - [{r.category.value}] {r.natural_language_rule}")
        out(
            f"      series={series_label}  quantifiability={r.quantifiability.value}  instrument_tags={r.instrument_tags}"
        )

    out("\n4. DISCRETIONARY / AI_ASSUMPTION RULES (never auto-enter a backtest without approval)")
    non_executable = [r for r in rules if r not in executable]
    for r in non_executable:
        series_label = series_by_id[r.series_id].series_name if r.series_id else "(no series)"
        out(
            f"  - [{r.category.value}] evidence_type={r.evidence_type.value} status={r.status.value}"
        )
        out(f'      "{r.natural_language_rule}"')
        out(
            f"      series={series_label}  quantifiability={r.quantifiability.value if r.quantifiability else None}"
        )

    out("\n5. CONTRADICTIONS DISCOVERED")
    if not contradictions:
        out("  (none)")
    for contradiction in contradictions:
        rule_a = db.query(Rule).filter(Rule.id == contradiction.rule_a_id).one()
        rule_b = db.query(Rule).filter(Rule.id == contradiction.rule_b_id).one()
        series_a = series_by_id[rule_a.series_id].series_name if rule_a.series_id else "(no series)"
        series_b = series_by_id[rule_b.series_id].series_name if rule_b.series_id else "(no series)"
        out(f"  - Rule A [{series_a}]: {rule_a.natural_language_rule}")
        out(f"    Rule B [{series_b}]: {rule_b.natural_language_rule}")
        out(f"    Explanation: {contradiction.explanation}")
        out(f"    Resolution: {contradiction.resolution.value} (unresolved until a human decides)")

    out("\n6. MODEL MOST SUITABLE FOR FIRST NASDAQ BACKTEST")
    nq_entry_rules = [
        r for r in executable if r.category.value == "ENTRY" and "NQ" in r.instrument_tags
    ]
    if nq_entry_rules:
        best = nq_entry_rules[0]
        best_series = series_by_id[best.series_id].series_name if best.series_id else "(no series)"
        out(f"  Candidate: the '{best_series}' Order Block + Fair Value Gap entry model.")
        out(f"    - Has an EXPLICIT, {best.quantifiability.value} ENTRY rule tagged for NQ.")
        out("    - Formal Model Backtest Readiness Score (source support / quantifiability / rule")
        out(
            "      completeness / NASDAQ relevance) is not yet implemented (tracked separately) — this"
        )
        out("      is a qualitative read of the same signals it will use.")
    else:
        out("  No EXPLICIT, quantifiable, NASDAQ-tagged ENTRY rule exists yet.")

    out("\n7. WHAT REMAINS BEFORE THAT BACKTEST CAN RUN")
    out(
        "  - Replace this synthetic fixture with real ICT transcripts via manual import (or lift the"
    )
    out("    network block) so extraction runs against actual source material.")
    out(
        "  - The Order Block/FVG model above has no stop-loss, take-profit, or position-sizing rule"
    )
    out(
        "    yet — the Strategy Auditor (completeness check) must flag these as missing rather than"
    )
    out("    inventing them.")
    out("  - Build the formal Model Backtest Readiness Score and the quantification workflow so a")
    out(
        "    PARTIALLY_QUANTIFIABLE rule like the kill-zone entry above gets an explicit, user-approved"
    )
    out("    numeric definition before it can compile.")
    out("  - Compile a StrategySpecification from the approved rule set and run it through the")
    out("    existing (already-built) backtest engine against real NQ/US100 historical data.")

    out("\n8. SEARCH SANITY CHECK (same code path exposed via /search)")
    results = search_service.search_knowledge(db, project.id, "order block", limit=5)
    for r in results:
        out(f"  - [{r.result_type}] {r.title}: {len(r.citations)} citation(s)")

    out("=" * 78)
    db.close()

    report_path = Path(__file__).resolve().parent.parent.parent / "ICT_FIXTURE_VALIDATION_REPORT.md"
    report_path.write_text("```\n" + "\n".join(lines) + "\n```\n")
    print(f"\nReport also written to {report_path}")


if __name__ == "__main__":
    pid = seed()
    if pid is not None:
        report(pid)
