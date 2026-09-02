# StrategyForge AI — Roadmap

## Phase 1 — MVP (this build)

- [x] Repo restructure, docs, folder layout
- [x] Database schema + migrations (users, projects, sources, videos,
      transcripts, chunks, embeddings, concepts, rules, contradictions,
      strategies, versions, specs, generated code, backtests, jobs, audit log)
- [x] Clerk authentication + user-scoped projects API
- [x] YouTube ingestion (video/playlist/channel detection, metadata,
      transcripts, chunking, cost estimation)
- [x] LLM provider abstraction (Anthropic + OpenAI) with structured output
- [x] Concept + rule extraction with mandatory source citations
- [x] Contradiction detection + resolution workflow
- [x] Strategy completeness checker
- [x] Rule review UI (approve/edit/reject, contradiction resolution)
- [x] Strategy compiler → `StrategySpecification` (versioned)
- [x] Pine Script generator
- [x] Python strategy generator (same spec as Pine)
- [x] Backtest engine (commission, slippage, sessions, sizing, long/short)
- [x] Performance dashboard (equity curve, metrics, trade list)
- [x] Strategy versioning + version comparison
- [x] Seed/demo data, Docker Compose, beginner-friendly README

**Explicitly deferred out of this pass** (stubbed with a clear
"not implemented" marker, never a fake success path):
- Stripe billing (no webhook handler, subscription table, or plan-gating
  exist yet — config variables are reserved in `.env.example` only)
- PDF/notes/website ingestion (interface designed so it's additive)
- Real commercial market-data vendor integration (CSV provider is the only
  working `MarketDataProvider` today)

## Phase 2

- Multi-source strategy synthesis (merge concepts/rules across many
  creators for one strategy)
- Advanced contradiction detection (temporal — "creator changed their mind
  over time" — not just direct conflicts)
- Walk-forward testing, Monte Carlo trade resequencing, parameter
  sensitivity sweeps (engine scaffolding lands in Phase 1; full UI + agent
  narration in Phase 2)
- Overfitting protection thresholds tuned from real usage data
- Advanced strategy reports (PDF export)
- PDF/notes/website source ingestion

## Phase 3

- TradingView webhook integration (signal relay only)
- Paper-trading integration
- Broker abstraction (`BrokerAdapter`, no live orders)
- Live signal monitoring dashboards
- Strategy drift monitoring (does live behavior still match the backtest
  assumptions?)

**Live-money autonomous execution is out of scope indefinitely** and is not
implemented in any phase of this roadmap without a separate, explicit
safety-gated design (multi-condition kill switches, human confirmation per
trade or per session, broker-side risk limits) that does not exist today.
