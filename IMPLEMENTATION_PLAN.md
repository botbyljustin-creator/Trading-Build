# US100 COMMAND — Implementation Plan

This document tracks the build plan for US100 COMMAND, a modular AI-assisted
trading analysis platform for NASDAQ-100 / US100 instruments. It is a living
document — update the status markers as phases complete.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## Guiding Constraints (do not violate)

- Deterministic financial math (position sizing, stops, P/L, R-multiples,
  exposure, daily-loss limits) is **plain Python code**, never AI-generated.
- Claude (Anthropic API) provides **contextual analysis only** — summaries,
  qualitative confidence, plain-language reasoning. It never invents prices
  or indicator values, and its output is stored separately from the
  deterministic `rule_score` (as `ai_confidence`), never blended into it
  silently.
- No live-money order execution in V1. `PaperBrokerAdapter` only. A
  `BrokerAdapter` interface exists so a real broker can be added later
  behind an explicit, multi-condition safety gate (see
  `docs/LIVE_TRADING_FUTURE.md`, written in Phase 10).
- All timestamps stored in UTC. Session/market-hours logic interprets time
  in `America/New_York` (DST-aware) at the presentation/session-engine
  boundary only.
- No look-ahead bias: indicators and strategies may only read candles up to
  and including the "current" bar at evaluation time.
- Fail closed: missing/stale/duplicate/malformed data, an unreachable risk
  engine, or an AI outage must stop the affected analysis rather than
  silently continuing with defaults.
- Every signal, score, AI call, risk decision, and verdict is persisted with
  the inputs that produced it, so it is reproducible after the fact.

## Key Engineering Decisions (V1)

| Area | Decision | Rationale |
|---|---|---|
| Backend framework | FastAPI + Pydantic v2 | async-friendly, strong typing, auto OpenAPI docs at `/docs` |
| ORM / migrations | SQLAlchemy 2.0 (sync) + Alembic | mature, explicit, easy to reason about for financial data integrity |
| DB driver | `psycopg` (binary) | modern maintained driver for Postgres |
| Background jobs | Celery + Redis (introduced Phase 5+ when the scanner/monitor need periodic execution) | matches spec; Redis is already required for caching/pub-sub, so no extra infra |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind | spec requirement; App Router gives server components for dashboard density |
| Charts | TradingView Lightweight Charts | spec requirement, free, performant for candlestick + overlays |
| AI provider | Anthropic Claude, via `anthropic` Python SDK | spec requirement; strict JSON-mode prompts, versioned |
| Notifications | Telegram Bot API (httpx) + `EmailNotifier` interface (SMTP impl deferred) | Telegram is the priority channel; email interface exists so a provider can be dropped in |
| Auth (V1) | Single-operator API key / session, no multi-tenant auth yet | this is a personal command center, not a SaaS; documented as a gap in `docs/SECURITY.md` |
| Testing | pytest (backend), Vitest/Playwright-ready structure (frontend, added when frontend logic exists) | spec requirement |
| Containerization | Docker Compose: `postgres`, `redis`, `backend`, `frontend` (worker service added Phase 5) | matches "up with one command" requirement |

## Phase Checklist

- [x] **Phase 1 — Foundations**: repo scaffold, Docker Compose, Postgres,
      Redis, FastAPI skeleton with structured logging + config, Next.js
      skeleton with Tailwind dark theme shell, `/api/v1/health` endpoint
      reporting DB/Redis/app status, backend pytest suite green.
- [ ] **Phase 2 — Market data foundation**: `MarketDataProvider` interface,
      `MockMarketDataProvider`, `CSVMarketDataProvider`,
      `TradingViewWebhookProvider` + `/api/webhooks/tradingview` (secret
      validation, schema validation, dedupe), `Candle`/`MarketData` models,
      synthetic candle generator clearly tagged `SIMULATED DATA`,
      deterministic indicator engine (EMA/RSI/ATR/VWAP/volume
      MA/rel-volume/swings/structure/opening range/prev-day levels/session
      levels) with unit tests proving no look-ahead.
- [ ] **Phase 3 — Scanner & strategies & signal engine**: `Session` engine
      (America/New_York, DST-safe, configurable sessions/no-trade windows),
      `ScanResult`, `Strategy` interface with 3 initial strategies (VWAP
      Trend Continuation, VWAP Reclaim/Rejection, Opening Range Breakout),
      configurable weighted `SignalScore` (0-100) with stored breakdown.
- [ ] **Phase 4 — Planning & risk**: `InstrumentSpecification` model,
      `TradePlanner` (entry/stop/targets, multiple stop/target methods,
      min R:R rejection), deterministic `RiskEngine` (position sizing,
      daily loss lock, consecutive-loss stop, exposure limits, conservative
      defaults) with thorough unit tests, `VerdictEngine`
      (APPROVE/WATCHLIST/REJECT/DATA_ERROR/RISK_BLOCKED).
- [ ] **Phase 5 — Paper trading & monitoring**: `BrokerAdapter` interface,
      `PaperBrokerAdapter` (spread/slippage/commission/execution delay),
      Celery + Redis worker introduced for periodic scanning/monitoring,
      `ActiveTradeMonitor` (MFE/MAE, R achieved, stop/target/invalidation
      detection), trade journal records.
- [ ] **Phase 6 — Dashboard**: Command Center, Signals, Paper Trades, Trade
      Journal, Analytics, Backtests, Strategies, Risk Settings, AI Analysis,
      System Health, Settings pages; Lightweight Charts integration.
- [ ] **Phase 7 — Telegram notifications**: alert formatting, throttling,
      dedupe, dashboard deep link.
- [ ] **Phase 8 — Claude AI analyst**: `AIAnalysisService`, strict JSON
      input/output schemas, versioned prompts, stored model/latency/tokens,
      graceful degradation ("AI unavailable" flag, deterministic pipeline
      continues).
- [ ] **Phase 9 — Backtesting & analytics**: event-driven backtester (no
      look-ahead), performance metrics, breakdowns, walk-forward scaffolding,
      analytics querying rejected + traded signals.
- [ ] **Phase 10 — Hardening**: full test coverage pass, rate limiting,
      input sanitization, audit log completeness pass, docs completion,
      deployment configuration for a VPS.

## Phase 1 — What Was Built

- Monorepo layout: `backend/`, `frontend/`, `docker/`, `docs/`.
- `docker-compose.yml`: `postgres:16`, `redis:7`, `backend` (FastAPI/uvicorn,
  hot reload), `frontend` (Next.js dev server). Named volumes for Postgres
  data. Healthchecks on `postgres` and `redis` gate backend startup.
- Backend: FastAPI app factory (`app/main.py`), `app/core/config.py`
  (pydantic-settings, `.env`-driven, no hardcoded secrets), structured
  logging via `structlog` (`app/core/logging.py`), SQLAlchemy engine/session
  scaffold (`app/core/db.py`) and a Redis client accessor
  (`app/core/redis_client.py`), declarative `Base` (`app/models/base.py`).
  `GET /api/v1/health` performs live DB (`SELECT 1`) and Redis (`PING`)
  checks and reports per-component + overall status without raising —
  infra outages are surfaced, not thrown as 500s, matching the fail-safe
  design principle used again for `System Health` in Phase 6.
  Alembic wired to `Settings.database_url` and the shared `Base.metadata`,
  ready for the first real model migration in Phase 2.
- Frontend: Next.js 14 App Router + TypeScript + Tailwind, dark-theme base
  layout (`US100 COMMAND` shell), a landing page that calls the backend
  health endpoint server-side and renders live component status — proves
  the frontend↔backend wire end to end.
- Tooling: `ruff` + `black` + `mypy` configured in `backend/pyproject.toml`;
  `pytest` suite (`backend/tests/test_health.py`) covers the health endpoint
  in both "all healthy" and "DB down" cases using dependency overrides —
  no real Postgres/Redis needed to run the suite in CI or this sandbox.
- `.env.example` documents every environment variable the whole system will
  eventually need (later phases' keys are present but inert until those
  phases wire them up), so `cp .env.example .env` is a one-time step.
- `README.md` has the exact local-dev commands.

Every module directory required by later phases
(`providers/ indicators/ scanner/ strategies/ signals/ ai/ planning/ risk/
monitoring/ trading/ backtesting/ analytics/ notifications/ repositories/
services/ workers/`) exists now as an empty, importable Python package so
the project structure matches the target architecture from day one; each
currently contains only an `__init__.py` and is explicitly not implemented
yet.

## Non-Goals for V1 (explicit)

- Real broker connectivity / live order placement.
- Multi-user auth, roles, or billing.
- Mobile app.
- Options/futures Greeks or margin modeling beyond `InstrumentSpecification`.
