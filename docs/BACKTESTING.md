# Backtesting

> **STATUS: STUB — not yet implemented.** This document will be written
> alongside the event-driven backtesting engine in **Phase 9** (see
> `IMPLEMENTATION_PLAN.md`). Nothing below is authoritative yet; it records
> intent so the eventual implementation has a fixed target.

## Planned contents

- How the event-driven backtester guarantees time-order integrity and zero
  look-ahead (candles are only ever visible to strategy code up to the
  "current" simulated timestamp).
- CSV historical data ingestion format and validation.
- Configurable spread, slippage, and commission models, and why perfect
  fills are never assumed.
- The full performance metric set: total trades, win rate, average
  win/loss, profit factor, expectancy, average R, total R, max drawdown,
  largest win/loss, consecutive wins/losses, Sharpe/Sortino ratios (where
  applicable).
- Performance breakdowns by strategy, weekday, hour, session, long/short,
  signal-score bucket, AI-confidence bucket, and volatility regime.
- Walk-forward testing methodology (training / validation / out-of-sample
  periods) and an explicit discussion of overfitting risk: **parameters
  must never be optimized and evaluated on the same period.**
- Why the backtester has zero dependency on the Claude API — it must be
  fully reproducible and runnable offline. Any AI-assisted historical
  analysis is a separate, explicitly non-deterministic experiment, never
  part of the core backtest loop.
