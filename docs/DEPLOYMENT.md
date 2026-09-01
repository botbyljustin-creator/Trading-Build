# Deployment

> **STATUS: STUB — not yet implemented.** Full VPS deployment guidance
> lands in **Phase 10** (see `IMPLEMENTATION_PLAN.md`), once the system has
> real trading logic worth deploying. Nothing below is authoritative yet.

## Current state (Phase 1)

Local development only, via `docker compose up --build` (see
`docs/SETUP.md`). Not deployed anywhere; not hardened for production
exposure.

## Planned contents

- Target shape: the same `postgres` / `redis` / `backend` / `frontend`
  containers from `docker-compose.yml`, plus a Celery worker + beat
  container (introduced Phase 5), behind a reverse proxy (Caddy or Nginx)
  terminating TLS.
- Secrets handling on the VPS: environment variables or Docker secrets,
  never committed, never baked into images.
- Production build changes needed for the frontend (`next build` +
  `next start` instead of the Phase 1 dev-server container) and for the
  backend (drop `--reload`, add a process manager / multiple uvicorn
  workers).
- Postgres backup/restore strategy and volume persistence on the VPS.
- Monitoring/alerting for the deployed system itself (distinct from the
  in-app System Health page) — container restarts, disk usage, TLS
  expiry.
- Rollout process: how a new version is deployed without disrupting an
  in-progress paper-trading session or losing audit-log continuity.
- Explicit confirmation that `LIVE_TRADING_ENABLED` remains `false` in any
  deployment until the safeguards in `docs/LIVE_TRADING_FUTURE.md` are
  implemented and independently reviewed.
