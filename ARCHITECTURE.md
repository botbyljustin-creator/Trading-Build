# US100 COMMAND — Architecture

## 1. Purpose

US100 COMMAND continuously analyzes NASDAQ-100 / US100 market data, detects
predefined trading setups, plans and risk-manages candidate trades, monitors
them, and presents everything on a professional dashboard. AI (Claude)
assists human/analytical judgment; it never performs deterministic financial
math and never places orders.

## 2. Pipeline

```
MARKET DATA
    |  (MarketDataProvider: Mock / CSV / TradingView webhook; later Polygon/Alpaca/IBKR)
    v
CANDLE STORE  (Postgres: raw + normalized OHLCV, per symbol/timeframe, UTC)
    v
INDICATOR ENGINE  (EMA/RSI/ATR/VWAP/volume/structure — causal only, no future bars)
    v
SESSION ENGINE  (America/New_York session windows, DST-safe, no-trade windows)
    v
SCANNER  (produces ScanResult: describes current market state, no approval)
    v
STRATEGY ENGINE  (Strategy implementations evaluate ScanResult -> StrategyCandidate)
    v
SIGNAL ENGINE  (deterministic 0-100 SignalScore with stored category breakdown)
    v
AI ANALYST (Claude)  (optional, structured-JSON-in/out, advisory only; stores rule_score
    |                  and ai_confidence separately)
    v
TRADE PLANNER  (entry/stop/targets, R:R computation, rejects below min R:R)
    v
RISK ENGINE  (InstrumentSpecification-aware position sizing, daily-loss lock,
    |          exposure limits — pure deterministic code)
    v
VERDICT ENGINE  (APPROVE / WATCHLIST / REJECT / DATA_ERROR / RISK_BLOCKED)
    v
ALERT (Telegram/Email) + PAPER TRADE (PaperBrokerAdapter)
    v
MONITOR (ActiveTradeMonitor: MFE/MAE, R achieved, exits)
    v
TRADE JOURNAL + ANALYTICS + BACKTESTING
```

Every arrow is a persisted, reproducible transition: each stage stores the
inputs it consumed alongside its output, so any signal can be replayed and
explained after the fact.

## 3. Module Boundaries (backend/app)

| Package | Responsibility | Notes |
|---|---|---|
| `core` | config, logging, DB session, Redis client | no trading logic |
| `providers` | `MarketDataProvider` implementations | swappable, symbol-mapping aware |
| `indicators` | pure functions over candle series | causal only, unit-tested against look-ahead |
| `scanner` | builds `ScanResult` from indicators + session | never approves/rejects |
| `strategies` | `Strategy` interface + concrete strategies | config-driven thresholds |
| `signals` | scoring engine, `SignalCandidate` | weights are config, breakdown is stored |
| `ai` | `AIAnalysisService`, prompt versions, Pydantic-validated Claude I/O | advisory only |
| `planning` | `TradePlanner`, stop/target methods | rejects sub-minimum R:R plans |
| `risk` | `RiskEngine`, `InstrumentSpecification` | deterministic, conservative defaults |
| `monitoring` | `ActiveTradeMonitor` | MFE/MAE, exit detection |
| `trading` | `BrokerAdapter` interface + `PaperBrokerAdapter` | no live execution in V1 |
| `backtesting` | event-driven backtester | no Claude dependency, no look-ahead |
| `analytics` | performance breakdowns over all qualified signals (traded or not) | |
| `notifications` | Telegram + `EmailNotifier` interface | throttled, deduped |
| `repositories` | DB access layer (SQLAlchemy) | isolates ORM from services |
| `services` | orchestrates the pipeline above | composition root for business logic |
| `workers` | Celery tasks (scanning cadence, monitoring cadence) | introduced Phase 5 |
| `api` | FastAPI routers, request/response schemas | thin, delegates to `services` |
| `models` | SQLAlchemy ORM models | one module per bounded concept |
| `schemas` | Pydantic request/response/DTO schemas | never reuse ORM models as API contracts |

## 4. Data & Time Handling

- All persisted timestamps are UTC (`timestamptz` columns).
- The Session Engine is the single place that converts UTC to
  `America/New_York` for session classification (pre-market, NY open,
  morning, midday, power hour, after-hours), using the `zoneinfo` database
  so DST transitions are handled correctly without manual offsets.
- Raw provider payloads (e.g. TradingView webhook bodies) are stored
  verbatim in `webhook_events` before normalization, so data integrity
  issues can be diagnosed after the fact and normalization bugs can be
  patched and replayed.
- Indicators are computed strictly from candles at or before the
  evaluation timestamp — no indicator function is given access to future
  bars; this is enforced structurally (functions take a slice ending at
  "now") and verified with dedicated look-ahead tests.
- Duplicate/stale/malformed data is detected at ingestion (webhook dedupe
  key, timestamp monotonicity checks, schema validation) and flagged;
  affected downstream analysis is skipped rather than proceeding on bad
  input (fail closed).

## 5. Instrument & Symbol Mapping

`US100`, `NAS100`, `USTEC`, `NDX`, `NQ`, `QQQ` all refer to
NASDAQ-100-linked instruments but are not fungible — a CFD point is not a
futures point is not an ETF share. Two configurable layers keep this
correct:

1. **Symbol mapping** (`app/core/config.py` / DB `instruments` table):
   maps broker/provider-specific ticker strings to an internal canonical
   instrument id.
2. **`InstrumentSpecification`** (`app/risk/instrument_spec.py`, Phase 4):
   `tick_size`, `tick_value`, `point_value`, `contract_multiplier`,
   `currency`, `minimum_quantity`, `quantity_increment` per instrument.
   The Risk Engine always sizes positions through this model — it never
   assumes a universal dollars-per-point value.

## 6. AI Boundary

`AIAnalysisService` (Phase 8) sends Claude a strict, schema-validated JSON
context (instrument, timeframes, indicator state, session, strategy
candidate, rule score, R:R — never a raw prompt built from string
concatenation of arbitrary data). Claude's response is parsed into a
Pydantic model (`summary`, `setup_quality`, `supporting_factors`,
`contradicting_factors`, `market_regime`, `warnings`, `confidence`,
`reasoning_summary`). `confidence` is stored as `ai_confidence`, a field
entirely separate from the deterministic `rule_score` computed by the
Signal Engine — the Verdict Engine reads both but the AI can never change
how `rule_score` was computed. If the AI call fails or times out, the
pipeline continues with `ai_confidence = null` and an `AI_UNAVAILABLE` flag
rather than blocking signal generation.

## 7. Fail-Safe Rules (enforced across the pipeline)

- No market data / stale market data → scanner marks `DATA_ERROR`, no
  signal is approved for that symbol/timeframe.
- Risk Engine unreachable or account balance invalid → `RISK_BLOCKED`, no
  trade plan is approved.
- Invalid stop (e.g. non-positive risk distance) → trade plan rejected.
- Claude API failure → deterministic pipeline continues, AI fields marked
  unavailable; verdict never silently upgrades because AI failed.
- Database unavailable → no trade execution (paper or otherwise); health
  endpoint reports the outage.
- Daily loss limit reached → Risk Engine hard-blocks all further trades for
  the session, independent of signal quality.

## 8. Deployment Shape (target)

Local dev: Docker Compose (`postgres`, `redis`, `backend`, `frontend`).
Future VPS deployment (documented in `docs/DEPLOYMENT.md`, Phase 10):
same containers behind a reverse proxy (e.g. Caddy/Nginx) with TLS,
Postgres on a persistent volume or managed instance, Celery worker + beat
as additional containers, secrets via environment/Docker secrets — never
committed to the repo.

## 9. Why These Choices

- **FastAPI + Pydantic**: request/response validation, self-documenting
  `/docs`, async-ready for provider/webhook I/O.
- **SQLAlchemy + Alembic**: explicit schema control and migration history
  for financial data that must never silently drift.
- **Postgres**: transactional integrity for money-adjacent records; good
  time-series ergonomics via `timestamptz` + indexes (partitioning can be
  added later if candle volume warrants it).
- **Celery + Redis** (from Phase 5): Redis is already required for caching
  and dedupe; reusing it as the Celery broker avoids adding another moving
  part, and Celery's periodic tasks fit the scan/monitor cadence.
- **Next.js + Tailwind + Lightweight Charts**: dense, professional,
  server-renderable dashboard; Lightweight Charts is purpose-built for
  candlestick + overlay rendering at the fidelity this UI needs.
