# StrategyForge AI — Security

## Authentication

Clerk-issued JWTs are verified against Clerk's published JWKS
(`app/security/clerk.py`) — `PyJWKClient` fetches and caches signing keys,
and `jwt.decode` requires `exp`/`iat`/`sub` claims and (when
`CLERK_ISSUER` is set) validates the issuer. No claim is trusted unless
the signature verifies.

`get_current_user` syncs the verified Clerk identity into our own `users`
table (create-if-missing, refresh email) so every other table foreign-keys
against a stable internal UUID rather than a third-party subject string
that could theoretically be reissued.

**`AUTH_DEV_MODE`** is a local-only escape hatch: with no `Authorization`
header and `AUTH_DEV_MODE=true`, requests authenticate as a single fixed
dev user — refused whenever `APP_ENV=production`
(`settings.is_production` short-circuits it in `get_current_claims`). This
exists so the full pipeline can be exercised without a Clerk account
during development; it must never be set in a deployed environment.

## Authorization / user data isolation

Every resource below a project (`Source`, `Video`, `Rule`, `Contradiction`,
`Strategy`, `StrategyVersion`, `Backtest`, `Job`, `Report`) is fetched
through a dedicated FastAPI dependency in `app/security/ownership.py` that
joins back to `Project.owner_id == current_user.id`. A resource that
exists but isn't owned by the caller returns **404, never 403** — an
authenticated user cannot use error codes to confirm another user's data
exists. There is no endpoint that queries these tables without going
through one of these dependencies.

## Secrets

- All API keys/secrets are `pydantic.SecretStr` in `app/core/config.py` —
  never rendered in logs, `repr()`, or FastAPI's `/docs`.
- LLM provider keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), Clerk's
  secret key, and the database URL live only in the backend's environment
  — never sent to the browser. The frontend only ever holds
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (a publishable key, not a secret by
  design) and `NEXT_PUBLIC_API_URL`.
- `.env` is gitignored; `.env.example` documents every variable without
  real values.

## Input validation

Every request body is a Pydantic model with explicit field constraints
(`min_length`, `gt=0`, enum types, etc. — see `app/api/routes/*.py`).
FastAPI rejects anything that doesn't validate before a route body ever
runs, which is also the primary SQL-injection defense in combination with
SQLAlchemy's parameterized queries — no route builds SQL by string
concatenation anywhere in this codebase.

## Prompt injection

Transcripts are third-party, untrusted text. See `AI_PIPELINE.md`'s
"Prompt injection defense" section for the full structural explanation
(fixed system prompts, delimited user turns, forced structured output,
and the human-approval gate before any extracted rule can affect a
strategy).

## Rate limiting

**Not implemented in this build.** FastAPI has no rate-limiting middleware
configured yet; this is a known gap for a production deployment (a reverse
proxy like Caddy/Nginx, or a library like `slowapi`, would be the
straightforward addition — tracked informally, not yet in ROADMAP.md as a
numbered phase item).

## CSRF

Not applicable in the current design: the API is a pure JSON API
authenticated via a bearer token in the `Authorization` header (Clerk
session JWT), not cookies, so there is no ambient-credential CSRF surface
to defend against the way there would be with cookie-based sessions.

## Webhook verification

**Not applicable yet** — no inbound webhooks exist in this build (no
Stripe integration; see ROADMAP.md). When Stripe billing is implemented,
its webhook handler must verify `Stripe-Signature` before trusting a
payload, matching the same "never trust unauthenticated input" posture as
everything above.

## Dependency & audit hygiene

- `backend/requirements.txt`/`requirements-dev.txt` pin exact versions.
- `frontend/package.json` pins exact versions for direct dependencies.
- `AuditLog` (Module: Audit Log) records who did what to which entity for
  every reproducibility-relevant mutation this build implements: source
  added, cost confirmed, concepts/rules extracted, contradictions
  detected/resolved, rule edited/approved/rejected, strategy compiled,
  code generated, backtest performed — append-only, written in the same
  transaction as the mutation it describes. Background-job actions
  (extraction, backtesting) log with `user_id=null` since jobs aren't
  currently tied to the triggering user's session; interactive actions log
  the real user. Parameter-sweep/optimization runs are not yet triggered
  from any API route (see BACKTESTING.md's robustness section and
  ROADMAP.md), so there is nothing to audit there yet.
