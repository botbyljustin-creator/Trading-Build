# StrategyForge AI — Database

PostgreSQL 16 + the `pgvector` extension (for transcript-chunk embeddings).
Schema is owned entirely by SQLAlchemy models (`backend/app/models/`) and
versioned with Alembic (`backend/alembic/versions/`) — there is no
hand-written DDL outside migrations, and `docker/postgres/init.sql`
deliberately contains none.

## Conventions

- Every table has a UUID primary key (`gen`'d in Python via `uuid.uuid4`,
  not database-side) and `created_at`/`updated_at` timestamps
  (`TIMESTAMPTZ`, UTC).
- Enums (`app/models/enums.py`) are stored as `VARCHAR` + `CHECK`
  (`native_enum=False`), not Postgres native enum types, so adding a member
  is a normal, low-risk migration rather than an `ALTER TYPE`.
- Foreign keys cascade (`ondelete="CASCADE"`) down the natural ownership
  tree (Project → Source → Video → Transcript → TranscriptChunk, etc.) so
  deleting a project cleans up everything under it; cross-cutting
  references (e.g. `reviewed_by_user_id`) use `SET NULL` instead.
- `pgvector`'s `Vector(1536)` type backs `embeddings.vector` — dimension
  matches OpenAI's `text-embedding-3-small`, the only embedding model
  currently wired up (see `AI_PIPELINE.md`).

## Entity groups

**Identity & workspace**
- `users` — one row per Clerk identity (`clerk_user_id` unique).
- `projects` — one research workspace per row, owned by a user.

**Source ingestion (Module 1)**
- `sources` — a submitted URL + its resolved type (video/playlist/channel)
  and cost-estimate fields.
- `videos` — one row per resolved YouTube video, with `transcript_status`.
- `transcripts` — one per video (1:1), full text + language.
- `transcript_chunks` — timestamped slices of a transcript, the unit
  extraction agents actually read.
- `embeddings` — one per chunk (1:1), the `pgvector` embedding. **Schema
  only in this build** — nothing currently writes to this table; V1's
  extraction agents read chunks directly and sequentially rather than via
  semantic search. Reserved for Phase 2 cross-source retrieval.

**Knowledge (Modules 2-4, 7)**
- `concepts` / `concept_sources` — extracted concepts and their required
  source citations.
- `concept_relations` — RELATED/CONFLICTING links between concepts.
- `rules` / `rule_sources` — extracted or user-authored trading rules,
  their category, status (`app.models.enums.RuleStatus`), and citations.
- `contradictions` — flagged conflicts between two `rules`, with a
  user-chosen `resolution`.

**Strategy compilation (Modules 5-6, 8-10)**
- `strategies` — a named strategy within a project.
- `strategy_versions` — one row per compile, with `completeness_score`,
  `missing_fields`, and the exact `rule_ids` that went into it.
- `strategy_specs` — the compiled `StrategySpecification` JSON (1:1 with a
  version) — the single source both code generators read.
- `generated_code` — Pine/Python text + a hash of the spec it was rendered
  from, one row per (version, language).

**Backtesting (Modules 11-14)**
- `backtests` — one row per run, with every input needed to reproduce it
  (provider/symbol/timezone/dates/costs/sizing — see `BACKTESTING.md`).
- `backtest_trades` — the trade list.
- `backtest_metrics` — the full metrics set (1:1 with a backtest),
  including the equity/drawdown curves and monthly returns as JSON.
- `optimization_runs` — robustness-test output (walk-forward, Monte Carlo,
  overfitting risk) tied to a backtest.

**Reporting & operations**
- `reports` — the assembled strategy report (Module: Reporting).
- `jobs` — durable record of every background task, polled by the frontend
  for progress (Module: Background Job System).
- `audit_log` — append-only record of reproducibility-relevant actions
  (Module: Audit Log) — never updated or deleted by application code.

## Migrations

```bash
# generate a new migration after changing a model
alembic revision --autogenerate -m "description"
# review the generated file — autogenerate misses some things (e.g. it
# does not know to add `CREATE EXTENSION vector`, already handled in the
# initial migration) — then apply it:
alembic upgrade head
```

Never edit an already-applied migration in place once it has run anywhere
outside your own machine — write a new migration instead, the same
discipline as any other shared codebase change.
