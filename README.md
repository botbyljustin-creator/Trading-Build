# US100 COMMAND

AI-assisted NASDAQ-100 / US100 trading **analysis** platform: continuous
market-data ingestion, deterministic technical scanning, strategy signal
scoring, AI-assisted contextual analysis, trade planning, risk management,
paper trading, monitoring, and a professional dashboard.

**This is not a live-money trading bot.** Deterministic Python code owns
every financial calculation (position sizing, stops, P/L, R-multiples,
exposure, daily-loss limits). Claude (Anthropic) provides advisory context
only — summaries, qualitative confidence, plain-language reasoning — and
is never in the path of a financial calculation or an order. V1 supports
signal generation, alerts, logging, backtesting, and paper trading; a
`BrokerAdapter` interface exists so real execution can be added later
behind an explicit, multi-condition safety gate (see
[`docs/LIVE_TRADING_FUTURE.md`](docs/LIVE_TRADING_FUTURE.md)).

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for the system design and
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for the phased build
plan and status.

## Quickstart

Requirements: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs (Swagger UI): http://localhost:8000/docs
- Backend health: http://localhost:8000/api/v1/health

Stop everything with `docker compose down` (add `-v` to also drop the
Postgres/Redis volumes — this deletes local data).

## What's implemented today (Phase 1)

- Dockerized Postgres 16 + Redis 7 with healthchecks.
- FastAPI backend with structured logging, environment-driven config (no
  hardcoded secrets), a SQLAlchemy/Alembic scaffold, and
  `GET /api/v1/health`, which reports live DB/Redis connectivity without
  ever raising — infrastructure outages are surfaced, not crashed on.
- Next.js 14 (App Router) + TypeScript + Tailwind dark-theme dashboard
  shell that renders the backend's health status server-side end to end.
- Every backend module package the full architecture will eventually use
  (`providers`, `indicators`, `scanner`, `strategies`, `signals`, `ai`,
  `planning`, `risk`, `monitoring`, `trading`, `backtesting`, `analytics`,
  `notifications`, `repositories`, `services`, `workers`) exists as an
  empty, documented Python package — see each `__init__.py` for which
  phase implements it.

Everything else described in this README's parent request (market data,
scanner, strategies, signal scoring, AI analysis, trade planning, risk
engine, paper trading, monitoring, dashboard pages, Telegram alerts,
backtesting, analytics) is **not yet implemented** — see
`IMPLEMENTATION_PLAN.md` for the phase checklist and do not assume any
unchecked item works.

## Local development without Docker (backend)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env   # then edit DATABASE_URL/REDIS_URL host to "localhost"
uvicorn app.main:app --reload
```

Run tests and checks:

```bash
cd backend
source .venv/bin/activate
pytest
ruff check app tests
black --check app tests
mypy app
```

## Local development without Docker (frontend)

```bash
cd frontend
npm install
INTERNAL_API_URL=http://localhost:8000 npm run dev
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Database migrations (Alembic)

Migrations run against `DATABASE_URL` from `Settings`. From inside the
`backend` container or a local venv with the DB reachable:

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

No models exist yet as of Phase 1, so there is nothing to migrate yet —
this becomes real starting Phase 2.

## Project structure

```
us100-command/
  backend/
    app/
      api/            FastAPI routers (thin, delegate to services)
      core/            config, logging, DB/Redis clients
      models/          SQLAlchemy ORM models
      schemas/         Pydantic request/response DTOs
      providers/       MarketDataProvider implementations
      indicators/      deterministic technical indicators
      scanner/         ScanResult generation
      strategies/      Strategy implementations
      signals/         deterministic signal scoring
      ai/              Claude-based AIAnalysisService (advisory only)
      planning/        TradePlanner
      risk/            RiskEngine, InstrumentSpecification
      monitoring/      ActiveTradeMonitor
      trading/         BrokerAdapter, PaperBrokerAdapter
      backtesting/     event-driven backtester
      analytics/       performance analytics
      notifications/   Telegram/email alerting
      repositories/    DB access layer
      services/        pipeline orchestration
      workers/         Celery tasks
    tests/
    alembic/
  frontend/
    app/               Next.js App Router pages
    components/
    lib/
    types/
  docker/
  docs/
  docker-compose.yml
  .env.example
```

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system design, data flow, module
  boundaries, key decisions.
- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — phased build plan
  and current status.
- [`docs/SETUP.md`](docs/SETUP.md) — detailed local setup.
- [`docs/TRADING_LOGIC.md`](docs/TRADING_LOGIC.md) — strategies, scoring
  (Phase 3+, stub for now).
- [`docs/RISK_ENGINE.md`](docs/RISK_ENGINE.md) — risk rules (Phase 4+, stub
  for now).
- [`docs/BACKTESTING.md`](docs/BACKTESTING.md) — backtesting methodology
  (Phase 9+, stub for now).
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — VPS deployment (Phase 10,
  stub for now).
- [`docs/SECURITY.md`](docs/SECURITY.md) — security posture and known gaps.
- [`docs/LIVE_TRADING_FUTURE.md`](docs/LIVE_TRADING_FUTURE.md) — the
  safeguards required before live execution could ever be enabled.

## License

Private project — no license granted for external use or redistribution.
