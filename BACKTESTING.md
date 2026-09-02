# StrategyForge AI — Backtesting

## Engine

`app/backtesting/engine.py::run_backtest(bars, signals, config)` is a
custom, event-driven, bar-by-bar simulator — not vectorbt or
backtesting.py. It was built in-house specifically so lookahead-bias
prevention, session handling, and cost modeling could be enforced
structurally and tested exhaustively (see `tests/test_backtest_engine.py`
and `tests/test_backtest_no_lookahead.py`), at the cost of raw throughput
vs. a vectorized engine — acceptable for the trade counts and CSV data
sizes V1 targets.

### No-lookahead guarantee

A decision made while processing bar `i` (a `long_entry`/`short_entry`
signal) is staged as a pending order and can only ever be **filled at bar
`i + 1`'s open** — never bar `i`'s own close. Stop/target checks for an
open position use the *current* bar's high/low, which is only ever a bar
at or after the fill bar. This is enforced by the code structure (a
pending-order variable that's only consumed at the top of the *next* loop
iteration), not just a convention.

This is verified by **truncation invariance** tests: running the engine on
the full dataset vs. a dataset truncated at time T produces byte-identical
trades/equity for everything strictly before T. If the engine ever peeked
at future bars to make an earlier decision, truncating the future would
change that earlier decision and the test would fail. A second test
overwrites all bars after a cutoff with random data and re-confirms the
same invariant. Run them directly:

```bash
pytest backend/tests/test_backtest_no_lookahead.py -v
```

### What the engine models

- **Commission**: flat per-trade (`commission_per_trade`) and/or
  percentage-of-notional (`commission_pct`), both applied on entry+exit.
- **Slippage**: `slippage_pct` applied against the fill price, unfavorably
  (long fills higher, short fills lower).
- **Position sizing**: risk-based — `quantity = (equity * risk_pct / 100) /
  stop_distance`. Sized off *realized* equity, not open unrealized P&L —
  documented, deliberate conservatism.
- **Sessions**: `allow_overnight=False` + `session_end_time` force-closes
  an open position at/after that local time (`session_timezone`); with no
  session end configured, positions can run to `END_OF_DATA`.
- **Max trades/day**: enforced per calendar day in `session_timezone`.
- **Long/short permission**: `allow_long`/`allow_short` gate entries
  independent of what the signal function proposes.
- **Same-bar stop+target ambiguity**: if one bar's range touches both the
  stop and the target, the engine assumes the **stop hit first** (the
  conservative assumption, since OHLC bars can't tell you the intrabar
  path) and records `exit_reason="STOP_TARGET_SAME_BAR_STOP_ASSUMED"` so
  this is visible in the trade list, not silently favorable.

### What it does not model (V1 limitations — stated, not hidden)

- No pyramiding / multiple concurrent positions — one position at a time.
- No partial fills or exchange-level order book effects.
- No borrow cost/availability for short positions.
- Bid/ask spread is only approximated via `slippage_pct`, not modeled as a
  separate two-sided cost.

## Data provider abstraction

`app/data_providers/base.py::MarketDataProvider` is the only interface the
engine's caller depends on (`get_historical_bars`, `get_symbol_info`,
`get_trading_calendar`). **CSV is the only implementation shipped in V1**
(`app/data_providers/csv_provider.py`): put `<symbol>.csv` (columns
`timestamp,open,high,low,close,volume`) and `<symbol>.meta.json`
(`{"timezone": "...", "asset_type": "...", "exchange_session": "..."}`) in
`Settings.market_data_csv_dir`. The metadata sidecar is **required** — the
provider raises rather than guessing a timezone/asset type, because an
instrument like "US100" is not one universal, interchangeable dataset (a
broker CFD point is not a CME future point is not a QQQ share — see
ARCHITECTURE.md §8). A commercial vendor integration is additive later
work behind the same interface.

## Every backtest run records its own identity

`Backtest.provider`, `.symbol`, `.timezone`, `.exchange_session`, and
`.asset_type` are stored on every run — reproducing a backtest six months
later means re-reading these fields, never assuming "the same US100 data"
means the same thing across two runs.

## Metrics (`app/backtesting/metrics.py`)

Net profit, total return %, CAGR (when the date range supports it),
max drawdown %, profit factor, win rate, avg win/loss, win/loss ratio,
expectancy, Sharpe/Sortino (computed on the **per-trade return series**,
not a continuous daily-return series — appropriate for a discretionary
strategy's typically modest trade count, but not directly comparable to a
daily-bar Sharpe from another tool), trade counts, largest win/loss,
max consecutive win/loss streaks, average holding period, full equity and
drawdown curves, monthly returns, and long/short breakdowns.

## Robustness & overfitting protection (Modules 13-14)

`app/backtesting/robustness.py`:
- `in_sample_out_of_sample_split` — simple time-ordered split.
- `walk_forward_windows` — rolling in/out-of-sample folds.
- `parameter_sensitivity` — full-grid sweep over a caller-supplied signal
  generator + parameter grid (reports the response surface; does not pick
  a "best" combination — Module 13's point is to see how sensitive results
  are, not to optimize).
- `monte_carlo_trade_resequencing` — bootstraps the *order* trades occurred
  in to show how much of the reported equity curve depends on a lucky/
  unlucky sequence, refusing to run (returning a clear note) below 5
  trades.
- `assess_overfitting_risk` — a deliberately simple, documented heuristic
  over parameter/combination/trade counts and in vs. out-of-sample
  degradation, returning LOW/MEDIUM/HIGH + reasons. This is the
  authoritative risk score; the Robustness Analyst LLM agent only narrates
  it, never computes or overrides it.

## Realism labeling (Module 12)

`app/services/backtest_service.py::_assumptions_notes` inspects the
compiled spec after a run and appends explicit notes whenever: a
bias/setup/confirmation/entry rule had no machine-translatable condition
(so it evaluated to always-false — see AI_PIPELINE.md), a stop/target was
`STRUCTURE_BASED` (text-only, no numeric level was applied), or no
position-sizing rule existed at all. These notes are stored on
`Backtest.assumptions_notes` and shown on the backtest page — a clean-
looking equity curve is never presented without also surfacing what wasn't
actually modeled.
