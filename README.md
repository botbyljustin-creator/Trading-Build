# StrategyForge AI

StrategyForge AI turns educational trading content — starting with
YouTube — into structured, testable trading systems. It ingests a video,
playlist, or channel, extracts the creator's actual trading concepts and
rules (with a source citation for every claim), flags what's missing,
ambiguous, or contradictory, and — only after a human reviews and approves
the rules — compiles a machine-readable strategy specification, generates
Pine Script and Python code from it, and runs a historical backtest.

**This tool does not promise a profitable trading system.** Its job is to
accurately translate trading education into explicit, falsifiable
hypotheses and evaluate them historically. It never invents a rule to make
a strategy "complete" — see [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
governing principle and how it's enforced in code, not just in the UI.

This README assumes no prior experience running a project like this —
every command is spelled out. If a step doesn't work, the "Troubleshooting"
section at the bottom covers the most common causes.

## What's real in this build

Everything described below actually runs — there are no placeholder
buttons pretending to work. What's genuinely **not** built yet (and is
labeled as such in the app itself, not hidden) is listed in
[`ROADMAP.md`](ROADMAP.md)'s "Explicitly deferred" section: Stripe billing,
PDF/website ingestion, and a commercial market-data vendor beyond CSV.
Concept/rule extraction and AI analyst commentary require you to supply
your own Anthropic or OpenAI API key — without one, those specific actions
return a clear error rather than a fake result.

## Prerequisites

You need these installed on your computer:

1. **Docker Desktop** (includes Docker Compose) — [docker.com/get-started](https://www.docker.com/get-started/).
   This is the only way most people should run this project; it starts
   Postgres, Redis, the backend, the background worker, and the frontend
   together with one command.
2. A **text editor** to fill in one configuration file (`.env`).
3. *(Optional, only if you want AI extraction to work)* an API key from
   [Anthropic](https://console.anthropic.com/) and/or
   [OpenAI](https://platform.openai.com/).
4. *(Optional, only if you want real user accounts instead of the built-in
   dev-mode user)* a free [Clerk](https://clerk.com/) account.

You do **not** need Python or Node.js installed on your machine to run
this via Docker — Docker provides both inside containers. They're only
needed for the "Running without Docker" section further down.

## Quickstart (Docker — recommended)

```bash
git clone <this-repository-url>
cd Trading-Build
cp .env.example .env
```

Open `.env` in your text editor. For a first run you can leave almost
everything as-is — the defaults work together out of the box. Two things
worth doing immediately:

- Generate a real `SECRET_KEY`:
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` (or use
  any random 40+ character string) and paste it in.
- If you have an Anthropic or OpenAI API key, paste it into
  `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. If you skip this, everything
  except AI extraction/analysis will still work.

Leave `AUTH_DEV_MODE=true` and the Clerk variables blank for now — you'll
be logged in automatically as a single local dev user. See
"Setting up real accounts with Clerk" below when you're ready for that.

Now start everything:

```bash
docker compose up --build
```

The first run downloads images and installs dependencies, so it can take a
few minutes. When it's ready you'll see the backend log `Application
startup complete`. Then open:

- **Frontend**: http://localhost:3000
- **Backend API docs (Swagger UI)**: http://localhost:8000/docs
- **Backend health check**: http://localhost:8000/api/v1/health

Stop everything with `Ctrl+C`, or `docker compose down` in another
terminal. Add `-v` to `docker compose down -v` if you also want to delete
the database (this deletes all your data — only do this if you mean to
start completely fresh).

### Load demo data (optional but recommended for a first look)

With the containers running, in a new terminal:

```bash
docker compose exec backend python scripts/seed_demo_data.py
```

This creates a project with a clearly-labeled **synthetic** (fabricated)
video transcript, and then runs the *real* pipeline over it — real
extracted concepts/rules, a real compiled strategy, real generated Pine
Script and Python code, and a real backtest with real metrics. It's the
fastest way to see every part of the app working. Refresh
http://localhost:3000 and you'll see it in the project switcher.

## Running the pipeline end to end

1. Open http://localhost:3000 and go to **Projects** → create one.
2. Go to **Sources**, paste a YouTube video/playlist/channel URL, click
   **Add**. StrategyForge AI detects which kind of URL it is and starts
   fetching metadata.
3. If the estimated processing cost is above the confirmation threshold
   (`LARGE_JOB_COST_CONFIRMATION_THRESHOLD_USD` in `.env`, default $2), a
   banner appears — click **Confirm & fetch transcripts** to proceed.
   Otherwise transcripts fetch automatically. Videos without available
   captions are marked `TRANSCRIPT_UNAVAILABLE` — never faked.
4. Go to **Knowledge** → **Rules** → **Extract rules** (and **Concepts** →
   **Extract concepts**). This calls your configured LLM provider — make
   sure you set an API key in `.env` first.
5. Review each rule. **Approve** the ones you agree with, **Edit** ones
   that need correction, **Reject** ones that don't apply. You can also
   **Add rule manually** to fill in something the extractor missed or
   couldn't structure. Run **Detect contradictions** and resolve any
   flagged conflicts.
6. Go to **Strategies** → create one → open it → **Compile new version**,
   selecting which approved rules to include. The completeness score and
   missing fields are shown immediately — nothing is filled in for you.
7. On the **Code** tab, click **Generate code** for Pine Script and Python.
8. On the **Backtests** tab, click **Run new backtest**. You'll need a CSV
   file of historical bars — see "Providing your own market data" below.
9. View results: equity curve, metrics, trade list, monthly returns. Run a
   **robustness test**, and generate a full **Strategy Report**.

## Providing your own market data

The only backtesting data source in this build is CSV files. Put files in
the directory `MARKET_DATA_CSV_DIR` points at (`./backend/data/market_csv`
by default when running via Docker, mounted as a volume):

- `<SYMBOL>.csv` with columns `timestamp,open,high,low,close,volume`
  (timestamp in any format `pandas.to_datetime` understands, ideally
  ISO-8601 with a UTC offset).
- `<SYMBOL>.meta.json`:
  ```json
  { "timezone": "America/New_York", "asset_type": "CFD", "exchange_session": "CME_GLOBEX" }
  ```

When creating a backtest, `symbol` must match `<SYMBOL>` exactly. See
[`BACKTESTING.md`](BACKTESTING.md) for why the metadata file is required
rather than assumed (a "US100" CFD, future, and ETF are not the same
instrument).

## Setting up real accounts with Clerk

1. Create a free application at [dashboard.clerk.com](https://dashboard.clerk.com/).
2. Copy its **Publishable key** and **Secret key**.
3. In `.env`, set `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (same value as
   `CLERK_PUBLISHABLE_KEY`), `CLERK_JWKS_URL` (found under your Clerk
   instance's API Keys page, or `https://<your-instance>.clerk.accounts.dev/.well-known/jwks.json`),
   and `CLERK_ISSUER` (your instance's frontend API URL).
4. Set `AUTH_DEV_MODE=false`.
5. `docker compose up --build` again (or restart the `backend` and
   `frontend` services).

## Running locally without Docker

Only do this if you have a specific reason to (e.g. active development
without container overhead). You'll need Python 3.12+, Node.js 20+,
PostgreSQL 16 with the `pgvector` extension, and Redis installed locally.

**Database:**
```bash
createdb strategyforge
psql strategyforge -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Backend:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env          # then edit DATABASE_URL to point at localhost
alembic upgrade head
uvicorn app.main:app --reload
```

**Celery worker** (separate terminal, same venv activated):
```bash
cd backend && source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```
Background jobs (ingestion, extraction, backtesting) sit `PENDING` forever
without this running — if actions in the UI never seem to complete, this
is almost always why.

**Redis** (separate terminal):
```bash
redis-server
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
cp .env.example .env.local 2>/dev/null || echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## Running tests

```bash
cd backend
source .venv/bin/activate   # or: docker compose exec backend bash
pip install -r requirements-dev.txt
pytest                       # unit tests — no external services needed
```

Some tests in `tests/test_api_integration.py` exercise the full pipeline
through real HTTP requests against a real Postgres database — they
auto-skip with a clear reason if no database is reachable, so `pytest`
alone always tells you what ran and what didn't.

Frontend:
```bash
cd frontend
npm run typecheck
npm run build   # also catches type/build errors across every page
```

## Database migrations

```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

See [`DATABASE.md`](DATABASE.md).

## Deployment

- **Frontend** → [Vercel](https://vercel.com/): point it at `frontend/`,
  set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` as
  project environment variables.
- **Backend, worker, Postgres, Redis** → [Railway](https://railway.app/)
  or any host that runs Docker containers: deploy `backend/Dockerfile` as
  two services (one running the default `uvicorn` command, one overriding
  the command to `celery -A app.workers.celery_app worker --loglevel=info`),
  plus managed Postgres (with `pgvector` — Railway's Postgres template
  supports this) and Redis add-ons.
- Set `APP_ENV=production` and **never** set `AUTH_DEV_MODE=true` in a
  deployed environment.
- Run `alembic upgrade head` as a release step before traffic hits a new
  version.

## Troubleshooting

- **"Backend down" / requests hang**: check `docker compose ps` — if
  `postgres` or `redis` isn't `healthy` yet, the backend waits for them.
  Give it another 10-15 seconds on first startup.
- **Jobs stay `PENDING` forever**: the Celery worker isn't running. Under
  Docker, check `docker compose logs worker`. Running locally, make sure
  you started the `celery -A app.workers.celery_app worker` process in
  its own terminal.
- **Extraction/analysis fails with "not configured"**: you haven't set
  `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`. This is intentional —
  the app never fabricates extraction results.
- **Backtest fails with "No CSV found"**: your CSV isn't in
  `MARKET_DATA_CSV_DIR`, or the `symbol` you entered doesn't match the
  filename exactly (case-sensitive).
- **Frontend shows "Dev mode · no auth configured"**: expected until you
  set up Clerk (see above) — not an error.

## Project documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system design, pipeline, agent
  architecture, fail-safe rules.
- [`DATABASE.md`](DATABASE.md) — schema and migration workflow.
- [`AI_PIPELINE.md`](AI_PIPELINE.md) — what calls an LLM, structured
  output, prompt-injection defenses, cost controls.
- [`BACKTESTING.md`](BACKTESTING.md) — engine internals, no-lookahead
  guarantees, what's and isn't modeled, robustness testing.
- [`SECURITY.md`](SECURITY.md) — auth, authorization, secrets, input
  validation.
- [`ROADMAP.md`](ROADMAP.md) — what's built, what's explicitly deferred,
  and what's planned next.
