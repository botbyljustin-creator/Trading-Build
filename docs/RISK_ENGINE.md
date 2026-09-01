# Risk Engine

> **STATUS: STUB — not yet implemented.** This document will be written
> alongside the `RiskEngine` and `InstrumentSpecification` implementation
> in **Phase 4** (see `IMPLEMENTATION_PLAN.md`). Nothing below is
> authoritative yet; it records intent so the eventual implementation has a
> fixed target.

## Planned contents

- Full input/output contract of `RiskEngine.evaluate(...)`.
- `InstrumentSpecification` fields (`tick_size`, `tick_value`, `point_value`,
  `contract_multiplier`, `currency`, `minimum_quantity`,
  `quantity_increment`) and why position sizing must never assume a
  universal dollars-per-point value across CFDs, futures, ETFs, and cash
  indices.
- Every configurable limit and its conservative default:
  - max risk per trade (default 0.5% of account)
  - max daily loss (default 2% of account) — hard-blocks all further
    trades for the remainder of the session once reached
  - max consecutive losses (default 3) — stop
  - max trades per day (default 3)
  - max simultaneous positions
  - max correlated exposure
  - minimum R:R (trade plans below this are rejected before reaching the
    Risk Engine)
  - maximum position size
- Rounding rules: rounding must never be allowed to increase risk above the
  configured maximum (round position size down, not to nearest).
- The full unit test matrix (daily-loss lock, consecutive-loss stop,
  zero/invalid stop distance, instrument-spec-aware sizing across multiple
  instrument types, exposure limit enforcement).
- Why the Risk Engine is 100% deterministic Python and never influenced by
  AI output — `ai_confidence` is read by the Verdict Engine downstream but
  never by the Risk Engine itself.
