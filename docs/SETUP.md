# Setup

## Prerequisites

- Docker + Docker Compose (primary supported path).
- For non-Docker local development: Python 3.12 and Node.js 22.

## First run

```bash
git clone <this repo>
cd Trading-Build
cp .env.example .env
docker compose up --build
```

Wait for the `backend` and `frontend` containers to report healthy (the
first build downloads and installs dependencies, which can take a few
minutes). Then:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

`GET /api/v1/health` returns `"status": "ok"` only once both Postgres and
Redis are reachable. Compose's healthchecks already gate backend startup
on Postgres/Redis being healthy, so a fresh `docker compose up` should
reach `"ok"` shortly after the containers start.

## Environment variables

See the comments in [`.env.example`](../.env.example) — every variable the
system will use across all phases is documented there, including which
ones are inert until a later phase implements the feature that reads them
(e.g. `ANTHROPIC_API_KEY` does nothing until Phase 8).

Never commit `.env`. `SECRET_KEY` should be generated per-environment:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Running backend checks locally (outside Docker)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check app tests
black --check app tests
mypy app
```

Note: `DATABASE_URL`/`REDIS_URL` in `.env.example` default to the Docker
Compose service hostnames (`postgres`, `redis`). Running the backend
directly on your host (not in a container) requires pointing those at
`localhost` instead, or running `docker compose up postgres redis` and
connecting to their published ports.

## Running frontend checks locally (outside Docker)

```bash
cd frontend
npm install
npm run typecheck
npm run lint
npm run build
```

## Resetting local data

```bash
docker compose down -v
```

This drops the Postgres and Redis volumes — all local signals, trades, and
cached state are lost. Use this if the database gets into a state you want
to discard during early development; do not run it against data you care
about.

## Troubleshooting

- **`/api/v1/health` shows `database: error`**: Postgres isn't reachable
  yet (still starting) or `DATABASE_URL` doesn't match the credentials in
  `.env`. Check `docker compose logs postgres`.
- **`/api/v1/health` shows `redis: error`**: same idea — check
  `docker compose logs redis`.
- **Frontend shows "backend down"**: the backend container isn't up yet,
  crashed, or `INTERNAL_API_URL`/`NEXT_PUBLIC_API_URL` are misconfigured.
  Check `docker compose logs backend`.
- **Port already in use**: another process is bound to 3000/8000/5432/6379
  on your host. Change the corresponding `*_PORT` variable in `.env`.
