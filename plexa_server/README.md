# Plexa Server

`plexa_server` is the lesson runtime and policy engine for Plexa.

It is responsible for:
- validating lesson artifacts
- enforcing lesson constraints
- managing session lifecycle
- orchestrating inference backends
- persisting lessons, courses, sessions, and logs

The server now supports both:
- a legacy filesystem storage backend
- a PostgreSQL storage backend using SQLAlchemy, Alembic, and `asyncpg`

## Layout

Key directories:

```text
plexa_server/
├── api/         # FastAPI app and route modules
├── auth/        # Auth helpers and request ownership checks
├── core/        # Session and lesson runtime logic
├── data/        # Legacy filesystem-backed development data
├── db/          # Database config, models, sessions, bootstrap
├── inference/   # Inference abstraction and stub backend
├── models/      # Pydantic domain models
├── storage/     # Filesystem and Postgres storage implementations
├── tests/       # Backend-aware test suite
├── utils/       # Import and supporting utilities
├── alembic/     # Database migrations
└── docker-compose.yml
```

## Local Development

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the server dependencies into that environment. At minimum, the database path requires:

```bash
python -m pip install sqlalchemy alembic asyncpg pytest
```

If `pytest` resolves to a system binary on your machine, prefer:

```bash
python -m pytest
```

## PostgreSQL Setup

This repository includes a local Postgres service definition in [docker-compose.yml](/home/kellan/projects/school/plexa/plexa_server/docker-compose.yml).

Start the database:

```bash
docker compose up -d
```

If your machine uses the older standalone Compose binary, use:

```bash
docker-compose up -d
```

The server-local [.env](/home/kellan/projects/school/plexa/plexa_server/.env) file defines the default development and test database URLs.

Important variables:
- `PLEXA_DATABASE_URL`
- `PLEXA_DATABASE_SYNC_URL`
- `PLEXA_TEST_DATABASE_URL`
- `PLEXA_TEST_DATABASE_SYNC_URL`
- `PLEXA_TEST_STORAGE_BACKEND`

## Database Bootstrap

The database bootstrap entrypoint is [db/bootstrap.py](/home/kellan/projects/school/plexa/plexa_server/db/bootstrap.py).

It can:
- wait for Postgres
- create the development and test databases
- run Alembic migrations
- optionally import the legacy filesystem dataset

Initialize both development and test databases:

```bash
python -m plexa_server.db.bootstrap --init-dev --init-test
```

Initialize both and import the filesystem dataset into each:

```bash
python -m plexa_server.db.bootstrap --init-dev --init-test --import-filesystem
```

Initialize only the development database:

```bash
python -m plexa_server.db.bootstrap --init-dev
```

Initialize only the test database:

```bash
python -m plexa_server.db.bootstrap --init-test
```

## Migrations

Alembic is configured in:
- [alembic.ini](/home/kellan/projects/school/plexa/plexa_server/alembic.ini)
- [alembic/env.py](/home/kellan/projects/school/plexa/plexa_server/alembic/env.py)

Run all migrations:

```bash
alembic upgrade head
```

Create a new revision:

```bash
alembic revision -m "describe schema change"
```

For schema updates driven from models, use autogeneration carefully:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Migrations are the authoritative schema workflow. The application should not rely on ad hoc table creation at startup.

## Importing Legacy Filesystem Data

The one-way importer lives at [utils/import_filesystem_to_postgres.py](/home/kellan/projects/school/plexa/plexa_server/utils/import_filesystem_to_postgres.py).

Import the filesystem dataset into the development database:

```bash
python -m plexa_server.utils.import_filesystem_to_postgres --target dev
```

Import it into the test database:

```bash
python -m plexa_server.utils.import_filesystem_to_postgres --target test
```

In normal local setup, it is simpler to let the bootstrap command handle this with `--import-filesystem`.

## Storage Backends

The active persistence implementations live under [storage](/home/kellan/projects/school/plexa/plexa_server/storage):

- [filesystem.py](/home/kellan/projects/school/plexa/plexa_server/storage/filesystem.py)
- [postgres.py](/home/kellan/projects/school/plexa/plexa_server/storage/postgres.py)
- [storage_interface.py](/home/kellan/projects/school/plexa/plexa_server/storage/storage_interface.py)

The application depends on the storage interfaces. Concrete backend selection happens in the composition root, not inside core session logic.

At this point:
- PostgreSQL is the primary backend
- filesystem storage remains available for legacy compatibility and comparative testing

## Running Tests

The test suite is backend-aware.

The default backend selector is read from:
1. an exported environment variable
2. [plexa_server/.env](/home/kellan/projects/school/plexa/plexa_server/.env)
3. the hard default `filesystem`

Set the backend in `.env`:

```env
PLEXA_TEST_STORAGE_BACKEND=filesystem
```

Supported values:
- `filesystem`
- `postgres`
- `both`

Run the full suite:

```bash
python -m pytest -q plexa_server/tests
```

Run backend-agnostic suites against both backends:

```bash
python -m pytest -q plexa_server/tests --storage-backend=both
```

Run only the Postgres-specific DB tests:

```bash
python -m pytest -q plexa_server/tests/db
```

Run only the API suite against Postgres:

```bash
python -m pytest -q plexa_server/tests/api --storage-backend=postgres
```

The backend-aware test wiring is centralized in [tests/conftest.py](/home/kellan/projects/school/plexa/plexa_server/tests/conftest.py).

## Running the API

The FastAPI app is constructed in [api/app.py](/home/kellan/projects/school/plexa/plexa_server/api/app.py).

You can interact with it over the terminal using `curl` once the server is running. Example:

```bash
curl http://127.0.0.1:8000/api/health
```

## Current Development Posture

The current intended development path is:
- PostgreSQL as the primary persistence layer
- Alembic migrations for schema changes
- `asyncpg` as the async driver under SQLAlchemy
- mostly full async runtime semantics
- filesystem storage retained only where it still provides value for testing or migration support
