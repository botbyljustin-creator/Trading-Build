# Trading Logic

> **STATUS: STUB — not yet implemented.** This document will be written
> alongside the Scanner, Strategy, and Signal Engine implementation in
> **Phase 3** (see `IMPLEMENTATION_PLAN.md`). Nothing below is authoritative
> yet; it records intent so the eventual implementation has a fixed target.

## Planned contents

- The Scanner → Strategy → Signal Engine pipeline in detail, with the exact
  `ScanResult` and `SignalCandidate` schemas.
- Each strategy's precise entry/confirmation/rejection rules, all
  parameterized via `strategy_configs` (nothing hardcoded):
  - VWAP Trend Continuation
  - VWAP Reclaim / Rejection
  - Opening Range Breakout
- The 0-100 signal scoring formula: every category, its weight, and how the
  stored breakdown maps back to the final score (trend, structure, volume,
  VWAP positioning, momentum, volatility, session quality, higher-timeframe
  confirmation, reward/risk potential, extension penalty).
- Explicit statement (already a project-wide rule, repeated here for
  emphasis): **these strategies are initial research strategies, not a
  claim of profitability.** All thresholds are backtestable and intended to
  be tuned/rejected using the backtesting and analytics modules, not taken
  on faith.
- How multi-timeframe confirmation works and how look-ahead bias is
  structurally prevented in the indicator/strategy evaluation path.
