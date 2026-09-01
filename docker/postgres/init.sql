-- Runs once, on first Postgres container initialization only (Docker only
-- executes files in /docker-entrypoint-initdb.d when the data directory is
-- empty). Alembic (backend/alembic) owns all actual schema migrations —
-- this file only guarantees the database/extensions the app expects exist.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
