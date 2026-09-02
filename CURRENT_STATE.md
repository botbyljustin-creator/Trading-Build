# StrategyForge AI — Current State

Snapshot after the ICT-integration pass on branch
`claude/strategyforge-ai-build-65sdzv` (HEAD `c768ecb`). This document is
the "inspect before you build" deliverable — it reflects what was actually
run and verified, not just what the code intends to do. Re-run the
commands under "How this was verified" to reproduce these findings.

## TL;DR

The V1 pipeline described in `ARCHITECTURE.md` is real and working, and it
now has everything needed to treat a large multi-series creator channel
(Inner Circle Trader is the first target) as a first-class dataset without
flattening distinct teachings together: a creator → series/playlist →
video hierarchy, evidence-type/quantifiability classification kept
separate from review-workflow status, a quantification workflow, a Model
Backtest Readiness Score per series, full-text knowledge search with
citations, and content-hash extraction caching. 96 backend tests pass, the
frontend typechecks and lints clean. What's proven end-to-end so far is a
clearly-labeled **synthetic fixture** dataset (`scripts/seed_ict_fixture.py`,
report in `ICT_FIXTURE_VALIDATION_REPORT.md`) — real ICT ingestion is still
blocked by this sandbox's network policy (below), so the next real step is
running this same, now-complete pipeline against actual ICT transcripts via
manual import or in an environment with YouTube egress.

**Hard constraint (still true)**: this sandboxed environment's network
policy blocks `youtube.com` outright (proxy returns 403 on CONNECT). No
amount of code fixes this from inside the session — real ICT ingestion has
to run somewhere with YouTube egress (your machine, or a normal
deployment), or via the manual transcript import path built this session.
See "Network constraint" below.

## Architecture (unchanged from ARCHITECTURE.md, confirmed accurate)

```
YouTube URL → Source Collector → Transcript Ingestion → Chunking
  → Knowledge Builder (LLM) → Rule Extractor (LLM) → Contradiction Analyst (LLM)
  → Strategy Auditor (deterministic) → Human Review
  → Strategy Architect (deterministic compile) → Code Generator (deterministic)
  → Backtest Engine (deterministic, no-lookahead) → Robustness scoring
  → Reporting Agent (templates already-validated data)
```

Backend: FastAPI + SQLAlchemy 2.0 + Alembic + Celery/Redis + Postgres 16
(pgvector installed, unused). Frontend: Next.js 14 App Router + TypeScript
+ Tailwind, Clerk-optional auth via a dev-mode fallback.

## Completed modules (verified working, not just present)

| Module | State | Evidence |
|---|---|---|
| DB schema (26 tables incl. `series`, `extraction_cache`, `rule_quantifications`) | Working | `alembic current` → head `65218d424d73` |
| Auth (Clerk + dev-mode) | Working | ownership dependencies tested via `test_api_integration.py` |
| YouTube URL classification | Working | 15 passing unit tests, all URL shapes |
| Playlist-aware channel ingestion (creator → series/playlist → video) | Working | `list_channel_playlists` + `resolve_source`; one `Series` per playlist, falls back to an "Uncategorized" series if a channel has none — never flattens |
| Manual transcript import (network-block workaround) | Working | `manual_import_service.py` + `POST /videos/manual-import`; matches `youtube_transcript_api`'s own output shape |
| Transcript fetch + chunking (live) | Working (code); **still untestable live** (network block) | `youtube_client.py`, `chunking.py` — logic unit-tested; live fetch never exercised in this sandbox |
| LLM provider abstraction (Anthropic/OpenAI) | Working | forced tool-use structured output, factory raises clearly without a key |
| Concept/Rule extraction agents, incl. evidence_type + quantifiability classification | Working (code); **never run against a real LLM this session** (no API key in this sandbox) | prompts + schemas classify EXPLICIT/IMPLIED/DISCRETIONARY/AI_ASSUMPTION and FULLY/PARTIALLY/DISCRETIONARY; persistence tested with a `FakeLLMProvider` |
| Content-hash extraction caching | Working | `ExtractionCache`; re-running extraction on unchanged chunks makes zero LLM calls (tested) |
| Deterministic instrument tagging (NQ/NASDAQ_100/US100/NAS100/...) | Working | `app/services/tagging.py`, never LLM-based |
| Contradiction detection | Working | service-layer logic, DB-level test; verified cross-series (never silently merges an evolved teaching) |
| Knowledge search with citations | Working | Postgres full-text search across concepts/rules/transcript chunks, series-scoped, every result cited — `GET /projects/{id}/search` |
| Model Backtest Readiness Score | Working | one score per series (source support / quantifiability / category completeness / NASDAQ relevance, contradiction-penalized) — `GET /projects/{id}/models/readiness` |
| Quantification workflow | Working | `RuleQuantification`; proposals always labeled separately from `Rule.natural_language_rule`, never auto-selected — `POST /rules/{id}/quantifications`, `POST /rule-quantifications/{id}/select` |
| Strategy compiler + completeness checker | Working | 7 unit tests, "never invents a missing field" verified |
| Pine Script + Python codegen (shared spec) | Working | equivalence tests confirm identical embedded spec JSON |
| Backtest engine | Working, well-tested | truncation-invariance lookahead tests, 8 engine tests, 3 metrics tests |
| Robustness (in/out-sample, walk-forward, Monte Carlo, overfitting score) | Working as a library; **only in/out-sample profit-factor split is wired to an API route** | `app/backtesting/robustness.py` fully unit-tested; walk-forward/sensitivity/Monte Carlo have no endpoint |
| Celery job system | Working | all 7 tasks register; exercised via eager-mode integration test |
| Frontend (Knowledge page: Search/Rules/Concepts/Models/Contradictions tabs, Sources page with manual import + series listing) | Working | `npx tsc --noEmit` and `next lint` both clean |
| Seed/demo data | Working | `scripts/seed_demo_data.py` (generic synthetic demo) and `scripts/seed_ict_fixture.py` (ICT-shaped fixture, full pipeline incl. contradiction detection + search) |

## Incomplete / not started

1. **Real ICT ingestion has not run.** Everything above is proven against
   a clearly-labeled *synthetic* fixture (`seed_ict_fixture.py`) because
   this sandbox cannot reach youtube.com. The pipeline is ready; it needs
   either real network egress or transcripts pasted in via manual import.
2. **Embeddings table is schema-only.** `Embedding` model + pgvector
   extension exist; nothing writes to it. Knowledge search uses Postgres
   full-text search instead (no embeddings-API cost or dependency) — this
   remains a reasonable v1 choice, not a gap to close by default.
3. **Model Backtest Readiness Score is a simple per-rule-ratio heuristic.**
   It does not yet weight by rule volume/coverage, so a series with one
   clean rule can outscore a larger series with more (but messier)
   material — worth revisiting once real data exposes this in practice.
4. **Robustness API surface is thin.** `run_robustness_task` only computes
   a simple in-sample/out-of-sample profit-factor split; the walk-forward,
   parameter-sensitivity, and Monte Carlo functions in
   `app/backtesting/robustness.py` are unit-tested but not reachable from
   any route.
5. **No StrategySpecification-lineage UI.** The data model supports full
   YouTube → Transcript → Source → Concept → Rule → StrategyRule lineage,
   but there's no dedicated view rendering that chain for a compiled
   version yet.
6. **Stripe billing**: not implemented (config placeholders only) —
   unchanged from `ROADMAP.md`, not in scope for this pass either.

## Network constraint (new finding this session)

Direct test from this sandbox:
```
$ curl -sS -o /dev/null -w "%{http_code}" https://www.youtube.com
000  (connection rejected by the egress proxy — org policy)
```
The proxy status endpoint confirms: `"detail": "gateway answered 403 to
CONNECT (policy denial or upstream failure)", "host": "www.youtube.com:443"`.

Consequence: `yt-dlp` and `youtube-transcript-api` calls fail in this
sandbox regardless of code correctness. The ingestion code is built and
unit-tested (with mocked network responses) so it works the moment it runs
in an environment with YouTube egress. In the meantime, the **manual
transcript import** path (`app/services/manual_import_service.py`, `POST
/projects/{id}/videos/manual-import`, and the "Manual transcript import"
form on the Sources page) lets real ICT transcripts — fetched by you, on a
machine that can reach YouTube, e.g. via `yt-dlp` or `youtube_transcript_api`
— be pasted in directly and flow through the identical extraction/citation/
contradiction/search pipeline used everywhere else. Everything used to
validate the pipeline *in this sandbox* (`scripts/seed_ict_fixture.py`,
`ICT_FIXTURE_VALIDATION_REPORT.md`) uses clearly-labeled synthetic fixture
text, never content presented as real ICT material.

## Technical debt

- Local dev Postgres has accumulated ~29 leftover projects from repeated
  pytest integration-test runs (no teardown fixture). Harmless (dev DB
  only, gitignored/ephemeral), but worth adding a teardown or a dedicated
  test schema later.
- `mypy` reports ~59 findings, almost all one of two accepted patterns:
  (a) `Session.get()` typed as `T | None` even where a row is known to
  exist because we just created it, and (b) FastAPI route handlers
  annotated with a Pydantic response type while actually returning the
  ORM instance (idiomatic `response_model=` usage). Not treated as bugs;
  not re-litigated here.
- No rate limiting on the API (documented as a known gap in `SECURITY.md`).

## How this was verified

```bash
cd backend && source .venv/bin/activate
alembic current                 # -> 65218d424d73 (head)
pytest -q                       # -> 96 passed
python -c "from app.main import create_app; print(len(create_app().routes))"  # -> 55
python scripts/seed_ict_fixture.py   # seeds + prints the fixture validation report
cd ../frontend && npx tsc --noEmit && npx next lint  # both clean
```

## Recommended next implementation steps

1. **Run this pipeline against real ICT content.** Either fetch a small
   set of transcripts yourself (`youtube_transcript_api` or `yt-dlp` on a
   machine with YouTube access) and paste them in via manual import, or
   run the app in an environment without this sandbox's network block.
2. Wire the walk-forward / sensitivity / Monte Carlo robustness functions
   to an API route (currently library-only).
3. Weight the Model Backtest Readiness Score by rule volume/coverage, not
   just per-rule ratios, once real multi-series data exposes the current
   heuristic's small-series bias.
4. Build a StrategySpecification-lineage view (YouTube → Transcript →
   Source → Concept → Rule → StrategyRule) for a compiled version.
5. Populate the `Embedding` table if/when semantic (not just full-text)
   search becomes worth its LLM-embedding cost.
