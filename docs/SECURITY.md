# Security

This document tracks the system's actual security posture as of the
current phase (Phase 1). Unlike the other `docs/*.md` stubs, this one is
kept current every phase, since security decisions compound.

## Current posture (Phase 1)

- **No secrets are hardcoded.** All credentials/keys/tokens are loaded from
  environment variables via `app.core.config.Settings` (pydantic-settings)
  and typed as `SecretStr` where sensitive, so they are never accidentally
  rendered in logs, `repr()`, or the FastAPI-generated OpenAPI docs.
  `.env` is gitignored; `.env.example` documents every variable with no
  real values.
- **CORS** is restricted to `CORS_ORIGINS` (defaults to
  `http://localhost:3000` only) rather than `*`.
- **No API keys are exposed to the frontend.** The Next.js app only ever
  calls the backend (server-side via `INTERNAL_API_URL`, client-side via
  `NEXT_PUBLIC_API_URL`); Anthropic/Telegram/broker credentials live only
  in the backend's environment and are never sent to the browser.
- **Health endpoint fails safe**: `/api/v1/health` never raises on a
  downstream outage (DB/Redis down) — it reports the outage as data. This
  same pattern will be reused for every later "is it safe to trade right
  now" check (data staleness, risk engine availability, etc).
- **Dependency posture**: `npm audit` currently reports residual advisories
  in `next`'s own bundled `postcss` and in `glob` pulled in transitively by
  `eslint-config-next` (dev-only tooling, not shipped to the browser, and
  the flagged `glob` CVE requires invoking the `glob` CLI directly, which
  this project never does). `next` itself is pinned to the latest patched
  `14.2.x` release, which resolves the critical Server Actions DoS/CVE
  present in earlier `14.2.x` releases. Re-audit (`npm audit`) each phase;
  revisit the Next.js major version in Phase 10 hardening if advisories
  remain.

## Known gaps (tracked, not yet addressed)

These are explicit, intentional gaps for Phase 1 — not oversights — and
must be closed before any production/VPS deployment (Phase 10):

- **No authentication/authorization on the API.** This is currently a
  single-operator local tool. Before any non-localhost deployment, the API
  needs at minimum an API-key or session mechanism protecting every
  non-health endpoint.
- **No rate limiting yet.** Required before the TradingView webhook
  endpoint (Phase 2) and any publicly reachable endpoint go live.
- **No webhook signature/secret validation yet** — required, and planned,
  for `POST /api/webhooks/tradingview` in Phase 2
  (`TRADINGVIEW_WEBHOOK_SECRET`).
- **No input sanitization framework yet** beyond Pydantic's own validation
  — revisited as user-facing write endpoints (risk settings, strategy
  config) are added from Phase 4 onward.
- **No secrets manager integration** — `.env` / container environment
  variables only for now; Docker secrets compatibility is a Phase 10 item.
- **Frontend Docker image is dev-mode only** (`npm run dev`, hot reload,
  source maps). Not suitable for any non-local deployment as-is; Phase 10
  adds a `next build && next start` production image.

## Rules that must never be violated (project-wide, enforced by design)

- AI (Claude) output is advisory only. It is never in the code path of
  position sizing, stop calculation, P/L, R-multiples, exposure limits, or
  order placement. See `ARCHITECTURE.md` section 6.
- No live-money order execution exists in V1. The `BrokerAdapter` interface
  and safety gate for eventually enabling it are documented in
  `docs/LIVE_TRADING_FUTURE.md`.
- The system fails closed: missing/stale/malformed data, an unreachable
  risk engine, or an AI outage stop the affected analysis rather than
  proceeding with defaults. See `ARCHITECTURE.md` section 7.
