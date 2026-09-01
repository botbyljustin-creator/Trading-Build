# Live Trading — Future Safeguards (NOT IMPLEMENTED, NOT ENABLED)

**Current state: live-money order execution does not exist in this
codebase.** `app/trading/` (Phase 5) will contain only a `BrokerAdapter`
interface and a `PaperBrokerAdapter` implementation. Placeholder
interfaces for real brokers (`InteractiveBrokersAdapter`,
`TradovateAdapter`, `GenericRESTBrokerAdapter`) may be added later as
unimplemented shells so the integration point is architecturally ready —
they will not place real orders when added, and will raise
`NotImplementedError` (or equivalent) rather than silently no-op, so a
misconfiguration is loud, not silent.

This document exists so that if/when real broker execution is ever added,
it is added deliberately, with every safeguard below in place from the
start — not retrofitted after the fact.

## Required conditions (ALL must hold, simultaneously, to place a live order)

1. `LIVE_TRADING_ENABLED=true` explicitly set in the deployment
   environment (defaults to `false`; see `.env.example`).
2. Explicit, validated broker credentials for a real account (not paper/demo
   credentials being reused).
3. An explicit account allowlist — the specific broker account id(s)
   authorized for live execution, checked on every order.
4. Risk Engine pass — the same deterministic `RiskEngine` used for paper
   trading, with no relaxed limits for live mode.
5. Data health pass — market data must be fresh, non-duplicated, and
   schema-valid (the same checks that block paper-trade approval today).
6. Strategy pass — the signal must have cleared the same deterministic
   strategy/scoring pipeline as any paper trade; AI confidence never
   substitutes for or overrides this.
7. Daily loss pass — the daily-loss lock must not already be tripped.
8. System health pass — DB, Redis, broker connectivity, and the app's own
   health endpoint must all report healthy immediately before order
   submission.
9. An explicit live-environment indicator, surfaced prominently in the
   dashboard UI (not just a backend flag) — the operator must always be
   able to see, at a glance, whether they are looking at paper or live
   state.
10. An emergency kill switch — a single action (API call and dashboard
    button) that immediately halts all new order submission, independent
    of every other condition above, and is tested as part of the live
    integration before it is trusted.

## Explicitly out of scope until all of the above exist

- No order is ever placed silently. Every live order attempt (successful
  or blocked) is written to the audit log with the full set of conditions
  evaluated.
- No shortcut that trades speed for any of the above (e.g. a "fast path"
  that skips the Risk Engine) is acceptable at any point, including during
  initial live-integration testing — test against a real broker's paper/
  sandbox account instead.
- Flipping `LIVE_TRADING_ENABLED=true` alone must never be sufficient by
  itself to cause a live order — the implementation must check all ten
  conditions independently, every time, not cache a single "is live mode
  on" boolean checked once at startup.

## Why this document exists now, in Phase 1

Writing the safety contract before the broker integration exists forces
the eventual `BrokerAdapter`/live-mode implementation to be built against
a fixed target, rather than having safeguards bolted on after a working
"happy path" is already written — which is exactly how live-trading
systems end up with the kind of silent-order or bypassed-risk-check bugs
this project's ground rules explicitly forbid.
