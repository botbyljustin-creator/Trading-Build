# StrategyForge AI — Current State

Snapshot as of this inspection pass, on branch `claude/strategyforge-ai-build-65sdzv`
(HEAD `0f0ef14`). This document is the "inspect before you build" deliverable —
it reflects what was actually run and verified, not just what the code
intends to do. Re-run the commands under "How this was verified" to
reproduce these findings.

## TL;DR

The V1 pipeline described in `ARCHITECTURE.md` is real and working:
project → YouTube source → transcript → concept/rule extraction → human
review → compiled strategy spec → Pine/Python codegen → backtest →
robustness → report. 57 backend tests pass, the API serves 48 routes, the
frontend builds and was walked through in a real browser. What's missing
is everything this session's task now asks for: ICT as a first real
dataset, a creator/series/playlist hierarchy (today ingestion is flat per
`Source`), evidence-type/quantifiability classification of rules, a
quantification workflow, knowledge search, and cost-control caching.

**Hard constraint discovered this session**: this sandboxed environment's
network policy blocks `youtube.com` outright (proxy returns 403 on
CONNECT). No amount of code fixes this from inside the session — real ICT
ingestion has to run somewhere with YouTube egress (your machine, or a
normal deployment). See "Network constraint" below for how this is being
worked around for now.

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
| DB schema (23 tables) | Working | `alembic current` → head; all tables created |
| Auth (Clerk + dev-mode) | Working | ownership dependencies tested via `test_api_integration.py` |
| YouTube URL classification | Working | 15 passing unit tests, all URL shapes |
| Transcript fetch + chunking | Working (code); **untestable live** (network block) | `youtube_client.py`, `chunking.py` — logic unit-tested; live fetch never exercised this session |
| LLM provider abstraction (Anthropic/OpenAI) | Working | forced tool-use structured output, factory raises clearly without a key |
| Concept/Rule extraction agents | Working (code); **never run against a real LLM this session** (no API key configured in this sandbox) | prompts + schemas exist, persistence path tested with fixture data at the service layer only |
| Contradiction detection | Working | service-layer logic, DB-level test |
| Strategy compiler + completeness checker | Working | 7 unit tests, "never invents a missing field" verified |
| Pine Script + Python codegen (shared spec) | Working | equivalence tests confirm identical embedded spec JSON |
| Backtest engine | Working, well-tested | truncation-invariance lookahead tests, 8 engine tests, 3 metrics tests |
| Robustness (in/out-sample, walk-forward, Monte Carlo, overfitting score) | Working as a library; **only in/out-sample profit-factor split is wired to an API route** | `app/backtesting/robustness.py` fully unit-tested; walk-forward/sensitivity/Monte Carlo have no endpoint |
| Celery job system | Working | all 7 tasks register; exercised via eager-mode integration test |
| Frontend (11 pages) | Working | `npm run build` succeeds, `next lint` clean, browser walkthrough screenshots taken |
| Seed/demo data | Working | `scripts/seed_demo_data.py` runs a full real pipeline pass over a synthetic transcript |

## Incomplete / not started (relevant to this session's task)

1. **No creator/series/playlist hierarchy.** `Source` → `Video` is flat:
   a CHANNEL source lists videos via yt-dlp's `/videos` tab with no
   playlist/series grouping. There is no `Series` model. This is the
   single biggest gap against this session's "do not flatten the ICT
   channel" requirement.
2. **Rule classification conflates two different things.** `RuleStatus`
   (EXTRACTED/AMBIGUOUS/CONTRADICTORY/USER_CONFIRMED/USER_MODIFIED/
   AI_ASSUMPTION/REJECTED) is a *review workflow* state. There is no
   separate *evidence-type* classification (EXPLICIT/IMPLIED/
   DISCRETIONARY/USER_DEFINED) or *quantifiability* classification
   (FULLY/PARTIALLY/DISCRETIONARY) as this session's spec requires.
3. **No quantification workflow.** Nothing proposes candidate numeric
   definitions for discretionary language (e.g. "displacement") separate
   from the original teaching, or stores a user's chosen quantification.
4. **No knowledge search.** No endpoint answers a natural-language
   question against ingested concepts/rules with citations.
5. **No content-hash caching.** `extraction_service.py` re-processes every
   chunk passed to it; nothing skips already-processed content by hash.
   Re-running extraction on the same source would re-spend LLM cost.
6. **Embeddings table is schema-only.** `Embedding` model + pgvector
   extension exist; nothing writes to it. Not required for the search
   approach being added now (keyword/full-text first), but worth noting.
7. **No manual transcript import.** Every transcript must come from a
   live YouTube fetch. Given the network constraint below, this is now
   also the practical way to get real ICT content into the system this
   session.
8. **Robustness API surface is thin.** `run_robustness_task` only computes
   a simple in-sample/out-of-sample profit-factor split; the walk-forward,
   parameter-sensitivity, and Monte Carlo functions in
   `app/backtesting/robustness.py` are unit-tested but not reachable from
   any route.
9. **Stripe billing**: not implemented (config placeholders only) — unchanged
   from `ROADMAP.md`, not in scope for this pass either.

## Network constraint (new finding this session)

Direct test from this sandbox:
```
$ curl -sS -o /dev/null -w "%{http_code}" https://www.youtube.com
000  (connection rejected by the egress proxy — org policy)
```
The proxy status endpoint confirms: `"detail": "gateway answered 403 to
CONNECT (policy denial or upstream failure)", "host": "www.youtube.com:443"`.

Consequence: `yt-dlp` and `youtube-transcript-api` calls will fail in this
session regardless of code correctness. The ingestion code is being built
and unit-tested (with mocked network responses) so it works the moment it
runs in an environment with YouTube egress. In the meantime, a **manual
transcript import** path is being added so real ICT transcripts (fetched
by you, on a machine that can reach YouTube, e.g. via `yt-dlp` or the
YouTube transcript panel) can be pasted/uploaded directly and flow through
the identical extraction/citation/contradiction pipeline. Anything used to
validate the pipeline *in this session* uses clearly-labeled synthetic
fixture text, never content presented as real ICT material.

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
alembic current                 # -> c1aa9750ea72 (head)
pytest -q                       # -> 57 passed
python -c "from app.main import app; print(len(app.routes))"  # -> 48
cd ../frontend && npm run build && npx next lint  # both clean
```

## Recommended next implementation steps (this session's priority order)

1. Series/creator/playlist schema + playlist-aware channel ingestion
   (directly fixes "don't flatten the channel").
2. Manual transcript import (unblocks real ICT content despite the
   network constraint).
3. Evidence-type + quantifiability fields on `Rule`, updated extraction
   prompts/schemas to populate them.
4. Knowledge search (keyword/full-text + LLM synthesis, cited).
5. Series/creator/market scoping filters on rules/concepts listing.
6. Quantification workflow (`RuleQuantification` model + endpoints).
7. Model Backtest Readiness Score (deterministic, reuses the completeness
   checker's approach).
8. Content-hash extraction caching.
9. Validate the whole chain with a small (3-10 "video") synthetic fixture
   set styled after ICT terminology, run through the real pipeline, and
   report concepts/rules/discretionary items/contradictions — standing in
   for the real ICT ingestion until it's run outside this sandbox.
